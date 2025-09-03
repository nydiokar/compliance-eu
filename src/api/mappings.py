from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_database_session, MappingCRUD, DatasetCRUD
from src.models import MappingResponse, MappingCreate
from src.logging_conf import get_logger

logger = get_logger("api.mappings")
router = APIRouter()


@router.get("/dataset/{dataset_id}", response_model=List[MappingResponse])
async def list_mappings(
    dataset_id: str,
    db: Session = Depends(get_database_session)
):
    """List all mappings for a dataset."""
    # Verify dataset exists
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    mappings = MappingCRUD.list(db, dataset_id)
    return mappings


@router.post("/", response_model=MappingResponse)
async def create_mapping(
    mapping: MappingCreate,
    db: Session = Depends(get_database_session)
):
    """Create a new mapping."""
    # Verify dataset exists
    dataset = DatasetCRUD.get(db, mapping.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    try:
        created_mapping = MappingCRUD.create(db, mapping)
        logger.info("Mapping created via API", 
                   mapping_id=created_mapping.id, 
                   dataset_id=mapping.dataset_id)
        return created_mapping
    except Exception as e:
        logger.error("Failed to create mapping", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create mapping")


@router.get("/{mapping_id}", response_model=MappingResponse)
async def get_mapping(
    mapping_id: str,
    db: Session = Depends(get_database_session)
):
    """Get mapping by ID."""
    mapping = MappingCRUD.get(db, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping


@router.get("/dataset/{dataset_id}/latest", response_model=MappingResponse)
async def get_latest_mapping(
    dataset_id: str,
    db: Session = Depends(get_database_session)
):
    """Get the latest active mapping for a dataset."""
    # Verify dataset exists
    dataset = DatasetCRUD.get(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    mapping = MappingCRUD.get_latest(db, dataset_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="No mapping found for dataset")
    
    return mapping