from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db import get_database_session, RunCRUD, DatasetCRUD, ArtifactCRUD
from src.models import RunResponse, RunCreate, RunUpdate, RunStatus, ArtifactResponse
from src.logging_conf import get_logger

logger = get_logger("api.runs")
router = APIRouter()


@router.get("/", response_model=List[RunResponse])
async def list_runs(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    status: Optional[RunStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_database_session)
):
    """List runs with optional filtering."""
    runs = RunCRUD.list(db, dataset_id=dataset_id, status=status, skip=skip, limit=limit)
    return runs


@router.post("/", response_model=RunResponse)
async def create_run(
    run: RunCreate,
    db: Session = Depends(get_database_session)
):
    """Create a new run."""
    # Verify dataset exists
    dataset = DatasetCRUD.get(db, run.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    try:
        created_run = RunCRUD.create(db, run)
        logger.info("Run created via API", run_id=created_run.id, dataset_id=run.dataset_id)
        return created_run
    except Exception as e:
        logger.error("Failed to create run", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create run")


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    db: Session = Depends(get_database_session)
):
    """Get run by ID."""
    run = RunCRUD.get(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.put("/{run_id}", response_model=RunResponse)
async def update_run(
    run_id: str,
    run_update: RunUpdate,
    db: Session = Depends(get_database_session)
):
    """Update a run."""
    run = RunCRUD.update(db, run_id, run_update)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    logger.info("Run updated via API", run_id=run_id)
    return run


@router.get("/{run_id}/artifacts", response_model=List[ArtifactResponse])
async def get_run_artifacts(
    run_id: str,
    db: Session = Depends(get_database_session)
):
    """Get all artifacts for a run."""
    # Verify run exists
    run = RunCRUD.get(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    artifacts = ArtifactCRUD.list(db, run_id)
    return artifacts


@router.get("/dataset/{dataset_id}/latest", response_model=RunResponse)
async def get_latest_successful_run(
    dataset_id: str,
    db: Session = Depends(get_database_session)
):
    """Get the latest successful run for a dataset."""
    # Verify dataset exists
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    run = RunCRUD.get_latest_successful(db, dataset_id)
    if not run:
        raise HTTPException(status_code=404, detail="No successful run found for dataset")
    
    return run