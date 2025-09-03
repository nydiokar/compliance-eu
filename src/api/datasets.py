from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db import get_database_session, DatasetCRUD
from src.models import DatasetResponse, DatasetCreate, DatasetUpdate
from src.logging_conf import get_logger

logger = get_logger("api.datasets")
router = APIRouter()


@router.get("/", response_model=List[DatasetResponse])
async def list_datasets(
    org_id: Optional[str] = Query(None, description="Filter by organization ID"),
    active_only: bool = Query(True, description="Show only active datasets"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_database_session)
):
    """List datasets with optional filtering."""
    datasets = DatasetCRUD.list(db, org_id=org_id, active_only=active_only, skip=skip, limit=limit)
    return datasets


@router.post("/", response_model=DatasetResponse)
async def create_dataset(
    dataset: DatasetCreate,
    db: Session = Depends(get_database_session)
):
    """Create a new dataset."""
    # Check if dataset with same name exists for this organization
    existing = DatasetCRUD.get_by_name(db, dataset.org_id, dataset.name)
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Dataset '{dataset.name}' already exists for organization '{dataset.org_id}'"
        )
    
    try:
        created_dataset = DatasetCRUD.create(db, dataset)
        logger.info("Dataset created via API", dataset_id=created_dataset.id, name=dataset.name)
        return created_dataset
    except Exception as e:
        logger.error("Failed to create dataset", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create dataset")


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_database_session)
):
    """Get dataset by ID."""
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: str,
    dataset_update: DatasetUpdate,
    db: Session = Depends(get_database_session)
):
    """Update a dataset."""
    dataset = DatasetCRUD.update(db, dataset_id, dataset_update)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    logger.info("Dataset updated via API", dataset_id=dataset_id)
    return dataset


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_database_session)
):
    """Delete a dataset."""
    success = DatasetCRUD.delete(db, dataset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    logger.info("Dataset deleted via API", dataset_id=dataset_id)
    return {"message": "Dataset deleted successfully"}