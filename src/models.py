from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean, 
    ForeignKey, JSON, Enum, UniqueConstraint, Index
)
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, ConfigDict
import json


Base = declarative_base()


class RunStatus(PyEnum):
    """Status of a data processing run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(PyEnum):
    """Types of artifacts generated during processing."""
    INPUT_FILE = "input_file"
    OUTPUT_CSV = "output_csv"
    OUTPUT_JSON = "output_json"
    OUTPUT_XML = "output_xml"
    OUTPUT_PDF = "output_pdf"
    METADATA = "metadata"
    ERROR_LOG = "error_log"
    VALIDATION_REPORT = "validation_report"
    MAPPING_PROFILE = "mapping_profile"


# SQLAlchemy Models

class Dataset(Base):
    """Dataset configuration and metadata."""
    __tablename__ = "datasets"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    profile = Column(String, nullable=False)  # e.g., "budget_execution_v1"
    schedule_cron = Column(String)  # cron expression for scheduling
    publish_target = Column(String)  # "ckan", "ftp", "none"
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    mappings = relationship("Mapping", back_populates="dataset", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="dataset", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_dataset_org_name"),
        Index("idx_dataset_org_profile", "org_id", "profile"),
    )


class Mapping(Base):
    """Mapping configurations for datasets."""
    __tablename__ = "mappings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    json_spec = Column(JSON, nullable=False)  # YAML mapping as JSON
    version = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    dataset = relationship("Dataset", back_populates="mappings")
    
    # Constraints
    __table_args__ = (
        Index("idx_mapping_dataset_version", "dataset_id", "version"),
    )


class Run(Base):
    """Processing run records."""
    __tablename__ = "runs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime)
    status = Column(Enum(RunStatus), default=RunStatus.PENDING)
    input_hash = Column(String)  # SHA-256 of input file
    output_hash = Column(String)  # SHA-256 of primary output
    message = Column(Text)  # Success message or error details
    
    # Processing metrics
    rows_processed = Column(Integer)
    rows_valid = Column(Integer)
    rows_invalid = Column(Integer)
    
    # External publishing info
    external_package_id = Column(String)  # CKAN package ID
    external_resource_id = Column(String)  # CKAN resource ID
    
    # Relationships
    dataset = relationship("Dataset", back_populates="runs")
    artifacts = relationship("Artifact", back_populates="run", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        Index("idx_run_dataset_started", "dataset_id", "started_at"),
        Index("idx_run_status_started", "status", "started_at"),
    )


class Artifact(Base):
    """Files and outputs generated during processing."""
    __tablename__ = "artifacts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    kind = Column(Enum(ArtifactKind), nullable=False)
    path = Column(String, nullable=False)  # relative to data directory
    checksum = Column(String, nullable=False)  # SHA-256
    size_bytes = Column(Integer)
    mime_type = Column(String)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    run = relationship("Run", back_populates="artifacts")
    
    # Constraints
    __table_args__ = (
        Index("idx_artifact_run_kind", "run_id", "kind"),
        Index("idx_artifact_checksum", "checksum"),
    )


# Pydantic Models for API

class DatasetBase(BaseModel):
    """Base dataset schema."""
    org_id: str
    name: str
    description: Optional[str] = None
    profile: str
    schedule_cron: Optional[str] = None
    publish_target: Optional[str] = "none"
    active: bool = True


class DatasetCreate(DatasetBase):
    """Schema for creating datasets."""
    pass


class DatasetUpdate(BaseModel):
    """Schema for updating datasets."""
    name: Optional[str] = None
    description: Optional[str] = None
    profile: Optional[str] = None
    schedule_cron: Optional[str] = None
    publish_target: Optional[str] = None
    active: Optional[bool] = None


class DatasetResponse(DatasetBase):
    """Schema for dataset responses."""
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MappingBase(BaseModel):
    """Base mapping schema."""
    json_spec: Dict[str, Any]
    version: int = 1
    active: bool = True


class MappingCreate(MappingBase):
    """Schema for creating mappings."""
    dataset_id: str


class MappingResponse(MappingBase):
    """Schema for mapping responses."""
    id: str
    dataset_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RunBase(BaseModel):
    """Base run schema."""
    status: RunStatus
    message: Optional[str] = None
    rows_processed: Optional[int] = None
    rows_valid: Optional[int] = None
    rows_invalid: Optional[int] = None


class RunCreate(BaseModel):
    """Schema for creating runs."""
    dataset_id: str
    input_hash: str


class RunUpdate(BaseModel):
    """Schema for updating runs."""
    status: Optional[RunStatus] = None
    finished_at: Optional[datetime] = None
    output_hash: Optional[str] = None
    message: Optional[str] = None
    rows_processed: Optional[int] = None
    rows_valid: Optional[int] = None
    rows_invalid: Optional[int] = None
    external_package_id: Optional[str] = None
    external_resource_id: Optional[str] = None


class RunResponse(RunBase):
    """Schema for run responses."""
    id: str
    dataset_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    external_package_id: Optional[str] = None
    external_resource_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ArtifactBase(BaseModel):
    """Base artifact schema."""
    kind: ArtifactKind
    path: str
    checksum: str
    size_bytes: Optional[int] = None
    mime_type: Optional[str] = None


class ArtifactCreate(ArtifactBase):
    """Schema for creating artifacts."""
    run_id: str


class ArtifactResponse(ArtifactBase):
    """Schema for artifact responses."""
    id: str
    run_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Database utilities

def get_latest_mapping(session: Session, dataset_id: str) -> Optional[Mapping]:
    """Get the latest active mapping for a dataset."""
    return (
        session.query(Mapping)
        .filter(
            Mapping.dataset_id == dataset_id,
            Mapping.active == True
        )
        .order_by(Mapping.version.desc(), Mapping.created_at.desc())
        .first()
    )


def get_latest_successful_run(session: Session, dataset_id: str) -> Optional[Run]:
    """Get the latest successful run for a dataset."""
    return (
        session.query(Run)
        .filter(
            Run.dataset_id == dataset_id,
            Run.status == RunStatus.COMPLETED
        )
        .order_by(Run.started_at.desc())
        .first()
    )


def cleanup_old_runs(session: Session, dataset_id: str, keep_last: int = 10) -> int:
    """Clean up old runs, keeping the most recent ones."""
    # Get run IDs to delete (keeping the most recent)
    runs_to_keep = (
        session.query(Run.id)
        .filter(Run.dataset_id == dataset_id)
        .order_by(Run.started_at.desc())
        .limit(keep_last)
        .subquery()
    )
    
    runs_to_delete = (
        session.query(Run)
        .filter(
            Run.dataset_id == dataset_id,
            ~Run.id.in_(runs_to_keep)
        )
        .all()
    )
    
    count = len(runs_to_delete)
    for run in runs_to_delete:
        session.delete(run)
    
    return count