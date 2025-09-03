from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn
from pathlib import Path

from src.settings import settings
from src.logging_conf import setup_logging, get_logger, RequestLoggingMiddleware
from src.db import get_database_session, init_database
from src.models import DatasetResponse, RunResponse
from src.api.datasets import router as datasets_router
from src.api.mappings import router as mappings_router
from src.api.runs import router as runs_router
from src.api.upload import router as upload_router

# Initialize logging
logger = setup_logging()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="EU Compliance Automation Kit - Schema-on-read pipeline for municipal and SME compliance",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Mount static files
static_path = Path(__file__).parent / "ui" / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Setup Jinja2 templates
templates_path = Path(__file__).parent / "ui" / "templates"
templates_path.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=templates_path)

# Include API routers
app.include_router(datasets_router, prefix="/api/datasets", tags=["datasets"])
app.include_router(mappings_router, prefix="/api/mappings", tags=["mappings"])
app.include_router(runs_router, prefix="/api/runs", tags=["runs"])
app.include_router(upload_router, prefix="/api/upload", tags=["upload"])


@app.on_event("startup")
async def startup_event():
    """Initialize database and other startup tasks."""
    logger.info("Starting Compliance Automation Kit", version=settings.app_version)
    
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup tasks on shutdown."""
    logger.info("Shutting down Compliance Automation Kit")


# Web UI Routes

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_database_session)):
    """Main dashboard page."""
    from src.db import DatasetCRUD, RunCRUD
    
    # Get recent datasets and runs for dashboard
    datasets = DatasetCRUD.list(db, limit=10)
    recent_runs = RunCRUD.list(db, limit=10)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "datasets": datasets,
        "recent_runs": recent_runs,
        "settings": settings
    })


@app.get("/datasets", response_class=HTMLResponse)
async def datasets_page(request: Request, db: Session = Depends(get_database_session)):
    """Datasets management page."""
    from src.db import DatasetCRUD
    
    datasets = DatasetCRUD.list(db, limit=100)
    
    return templates.TemplateResponse("datasets.html", {
        "request": request,
        "datasets": datasets,
        "settings": settings
    })


@app.get("/datasets/{dataset_id}", response_class=HTMLResponse)
async def dataset_detail(request: Request, dataset_id: str, db: Session = Depends(get_database_session)):
    """Dataset detail page."""
    from src.db import DatasetCRUD, RunCRUD, MappingCRUD
    
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    runs = RunCRUD.list(db, dataset_id=dataset_id, limit=20)
    mappings = MappingCRUD.list(db, dataset_id)
    
    return templates.TemplateResponse("dataset_detail.html", {
        "request": request,
        "dataset": dataset,
        "runs": runs,
        "mappings": mappings,
        "settings": settings
    })


@app.post("/ui/datasets", response_class=HTMLResponse)
async def ui_create_dataset(
    request: Request,
    org_id: str = Form(...),
    name: str = Form(...),
    profile: str = Form(...),
    description: str = Form(None),
    schedule_cron: str = Form(None),
    publish_target: str = Form("none"),
    db: Session = Depends(get_database_session)
):
    from src.models import DatasetCreate
    from src.db import DatasetCRUD

    try:
        # Prevent duplicates per org/name
        existing = DatasetCRUD.get_by_name(db, org_id, name)
        if existing:
            return HTMLResponse(
                content=f'<div class="alert alert-warning">Dataset "{name}" already exists for {org_id}</div>',
                status_code=200,
            )

        created = DatasetCRUD.create(db, DatasetCreate(
            org_id=org_id,
            name=name,
            profile=profile,
            description=description,
            schedule_cron=schedule_cron,
            publish_target=publish_target
        ))
        return HTMLResponse(
            content=(
                f'<div class="alert alert-success">'
                f'Created dataset <strong>{created.name}</strong> '
                f'(<code>{created.id}</code>)</div>'
            ),
            status_code=200,
        )
    except Exception as e:
        return HTMLResponse(
            content=f'<div class="alert alert-danger">Failed to create dataset: {str(e)}</div>',
            status_code=200,
        )


@app.get("/ui/datasets/options", response_class=PlainTextResponse)
async def ui_dataset_options(db: Session = Depends(get_database_session)):
    from src.db import DatasetCRUD
    datasets = DatasetCRUD.list(db, limit=100)
    # Return raw <option> list suitable for HTMX swap
    options = ["<option value=\"\">Select dataset for mapping suggestions...</option>"]
    for d in datasets:
        options.append(f'<option value="{d.id}">{d.name} ({d.org_id})</option>')
    return PlainTextResponse("\n".join(options))


@app.get("/mappings/{dataset_id}", response_class=HTMLResponse)
async def mapping_page(request: Request, dataset_id: str, db: Session = Depends(get_database_session)):
    """Mapping configuration page."""
    from src.db import DatasetCRUD, MappingCRUD
    from src.core.mapping import list_profiles
    
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    current_mapping = MappingCRUD.get_latest(db, dataset_id)
    available_profiles = list_profiles()
    
    return templates.TemplateResponse("mapping.html", {
        "request": request,
        "dataset": dataset,
        "current_mapping": current_mapping,
        "available_profiles": available_profiles,
        "settings": settings
    })


@app.get("/runs/{dataset_id}", response_class=HTMLResponse)
async def runs_page(request: Request, dataset_id: str, db: Session = Depends(get_database_session)):
    """Runs history page."""
    from src.db import DatasetCRUD, RunCRUD, ArtifactCRUD
    
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    runs = RunCRUD.list(db, dataset_id=dataset_id, limit=50)
    
    # Add artifacts to runs
    for run in runs:
        run.artifacts = ArtifactCRUD.list(db, run.id)
    
    return templates.TemplateResponse("runs.html", {
        "request": request,
        "dataset": dataset,
        "runs": runs,
        "settings": settings
    })


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """File upload page."""
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "settings": settings
    })


# API Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}


if __name__ == "__main__":
    uvicorn.run(
        "src.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_config=None,  # We handle logging ourselves
    )
