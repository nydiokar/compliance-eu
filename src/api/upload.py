import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from src.db import get_database_session, DatasetCRUD
from src.core.intake import load_frame
from src.core.mapping import detect_headers, find_column_matches
from src.settings import settings
from src.logging_conf import get_logger

logger = get_logger("api.upload")
router = APIRouter()


@router.post("/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    dataset_id: Optional[str] = Form(None),
    db: Session = Depends(get_database_session)
):
    """Analyze uploaded file and suggest mappings."""
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_extension = Path(file.filename).suffix.lower().lstrip('.')
    allowed = {e.lower().lstrip('.') for e in settings.allowed_file_extensions}
    if file_extension not in allowed:
        raise HTTPException(
            status_code=400, 
            detail=f"File type .{file_extension} not allowed. Allowed types: {settings.allowed_file_extensions}"
        )
    
    # Save uploaded file temporarily
    temp_dir = settings.upload_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    temp_file = temp_dir / file.filename
    try:
        # Save file
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info("File uploaded for analysis", filename=file.filename, size=temp_file.stat().st_size)
        
        # Parse file
        df = load_frame(temp_file)
        
        # Detect headers
        header_row, detected_headers = detect_headers(df)
        
        # Get sample data (first 10 rows after headers)
        sample_start = header_row + 1
        sample_data = df.iloc[sample_start:sample_start+10].to_dict('records')
        
        result = {
            "filename": file.filename,
            "file_size": temp_file.stat().st_size,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "header_row": header_row,
            "detected_headers": detected_headers,
            "sample_data": sample_data,
            "data_preview": df.head(10).to_dict('records')
        }
        
        # If dataset_id provided, suggest mappings
        if dataset_id:
            dataset = DatasetCRUD.get(db, dataset_id)
            if dataset:
                # TODO: Load profile and suggest mappings
                # This would use the mapping profile to suggest column mappings
                result["dataset_profile"] = dataset.profile
                result["suggested_mappings"] = {}  # Placeholder
        
        return result
        
    except Exception as e:
        logger.error("File analysis failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to analyze file: {str(e)}")
    
    finally:
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()


@router.post("/process")
async def process_file(
    file: UploadFile = File(...),
    dataset_id: str = Form(...),
    column_mapping: str = Form(...),  # JSON string of column mappings
    db: Session = Depends(get_database_session)
):
    """Process uploaded file with specified mappings."""
    # Verify dataset exists
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_extension = Path(file.filename).suffix.lower().lstrip('.')
    allowed = {e.lower().lstrip('.') for e in settings.allowed_file_extensions}
    if file_extension not in allowed:
        raise HTTPException(
            status_code=400, 
            detail=f"File type .{file_extension} not allowed"
        )
    
    # Save to uploads/dataset_id and process synchronously via pipeline
    from src.core.pipeline import process_file_pipeline
    from src.models import Dataset
    
    dataset_dir = settings.upload_dir / dataset.org_id / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    saved_path = dataset_dir / file.filename
    try:
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info("File saved for processing", path=str(saved_path))
        
        # Run pipeline using dataset profile and org
        org_id = dataset.org_id
        profile_name = dataset.profile
        result = process_file_pipeline(
            file_path=saved_path,
            dataset_id=dataset_id,
            profile_name=profile_name,
            org_id=org_id,
            metadata={
                "title": f"{dataset.name} - {org_id}",
                "publisher": org_id,
                "profile": profile_name,
            }
        )
        
        return {"message": "Processing completed", "run_id": result.get("run_id"), "exports": {
            k: str(v) for k, v in result.get("exports", {}).items() if k in ("csv", "json", "metadata")
        }}
    except Exception as e:
        logger.error("Processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/status/{run_id}")
async def get_processing_status(
    run_id: str,
    db: Session = Depends(get_database_session)
):
    """Get status of file processing job."""
    from src.db import RunCRUD
    
    run = RunCRUD.get(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return {
        "run_id": run_id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "message": run.message,
        "rows_processed": run.rows_processed,
        "rows_valid": run.rows_valid,
        "rows_invalid": run.rows_invalid
    }
