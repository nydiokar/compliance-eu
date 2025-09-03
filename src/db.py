from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.settings import settings
from src.models import Base
from src.logging_conf import get_logger

logger = get_logger("database")


def _enable_foreign_keys(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_database_engine():
    """Create database engine with appropriate configuration."""
    # SQLite-specific configuration
    connect_args = {}
    poolclass = StaticPool
    
    if settings.database_url.startswith("sqlite"):
        connect_args = {
            "check_same_thread": False,  # Allow multi-threading
            "timeout": 30,  # Connection timeout
        }
    
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        poolclass=poolclass,
        echo=settings.debug,  # Log SQL queries in debug mode
        echo_pool=settings.debug,
    )
    
    # Enable foreign keys for SQLite
    if settings.database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_foreign_keys)
    
    return engine


# Create global engine and session factory
engine = create_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database():
    """Initialize database by creating all tables."""
    logger.info("Initializing database")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


def get_database_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager to get database session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session() -> Session:
    """Get a new database session (must be closed manually)."""
    return SessionLocal()


# CRUD Operations

from src.models import (
    Dataset, DatasetCreate, DatasetUpdate,
    Mapping, MappingCreate, 
    Run, RunCreate, RunUpdate,
    Artifact, ArtifactCreate,
    RunStatus
)
from typing import List, Optional
from datetime import datetime


class DatasetCRUD:
    """CRUD operations for datasets."""
    
    @staticmethod
    def create(db: Session, dataset: DatasetCreate) -> Dataset:
        """Create a new dataset."""
        db_dataset = Dataset(**dataset.dict())
        db.add(db_dataset)
        db.commit()
        db.refresh(db_dataset)
        logger.info("Created dataset", dataset_id=db_dataset.id, name=dataset.name)
        return db_dataset
    
    @staticmethod
    def get(db: Session, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by ID."""
        return db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    @staticmethod
    def get_by_name(db: Session, org_id: str, name: str) -> Optional[Dataset]:
        """Get dataset by organization and name."""
        return db.query(Dataset).filter(
            Dataset.org_id == org_id,
            Dataset.name == name
        ).first()
    
    @staticmethod
    def list(db: Session, org_id: str = None, active_only: bool = True, skip: int = 0, limit: int = 100) -> List[Dataset]:
        """List datasets with filtering."""
        query = db.query(Dataset)
        if org_id:
            query = query.filter(Dataset.org_id == org_id)
        if active_only:
            query = query.filter(Dataset.active == True)
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def update(db: Session, dataset_id: str, dataset_update: DatasetUpdate) -> Optional[Dataset]:
        """Update a dataset."""
        db_dataset = DatasetCRUD.get(db, dataset_id)
        if not db_dataset:
            return None
        
        update_data = dataset_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_dataset, field, value)
        
        db.commit()
        db.refresh(db_dataset)
        logger.info("Updated dataset", dataset_id=dataset_id)
        return db_dataset
    
    @staticmethod
    def delete(db: Session, dataset_id: str) -> bool:
        """Delete a dataset."""
        db_dataset = DatasetCRUD.get(db, dataset_id)
        if not db_dataset:
            return False
        
        db.delete(db_dataset)
        db.commit()
        logger.info("Deleted dataset", dataset_id=dataset_id)
        return True


class MappingCRUD:
    """CRUD operations for mappings."""
    
    @staticmethod
    def create(db: Session, mapping: MappingCreate) -> Mapping:
        """Create a new mapping."""
        db_mapping = Mapping(**mapping.dict())
        db.add(db_mapping)
        db.commit()
        db.refresh(db_mapping)
        logger.info("Created mapping", mapping_id=db_mapping.id, dataset_id=mapping.dataset_id)
        return db_mapping
    
    @staticmethod
    def get(db: Session, mapping_id: str) -> Optional[Mapping]:
        """Get mapping by ID."""
        return db.query(Mapping).filter(Mapping.id == mapping_id).first()
    
    @staticmethod
    def get_latest(db: Session, dataset_id: str) -> Optional[Mapping]:
        """Get the latest active mapping for a dataset."""
        return (
            db.query(Mapping)
            .filter(Mapping.dataset_id == dataset_id, Mapping.active == True)
            .order_by(Mapping.version.desc(), Mapping.created_at.desc())
            .first()
        )
    
    @staticmethod
    def list(db: Session, dataset_id: str) -> List[Mapping]:
        """List all mappings for a dataset."""
        return (
            db.query(Mapping)
            .filter(Mapping.dataset_id == dataset_id)
            .order_by(Mapping.version.desc(), Mapping.created_at.desc())
            .all()
        )


class RunCRUD:
    """CRUD operations for runs."""
    
    @staticmethod
    def create(db: Session, run: RunCreate) -> Run:
        """Create a new run."""
        db_run = Run(**run.dict())
        db.add(db_run)
        db.commit()
        db.refresh(db_run)
        logger.info("Created run", run_id=db_run.id, dataset_id=run.dataset_id)
        return db_run
    
    @staticmethod
    def get(db: Session, run_id: str) -> Optional[Run]:
        """Get run by ID."""
        return db.query(Run).filter(Run.id == run_id).first()
    
    @staticmethod
    def list(db: Session, dataset_id: str = None, status: RunStatus = None, skip: int = 0, limit: int = 100) -> List[Run]:
        """List runs with filtering."""
        query = db.query(Run)
        if dataset_id:
            query = query.filter(Run.dataset_id == dataset_id)
        if status:
            query = query.filter(Run.status == status)
        return query.order_by(Run.started_at.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def update(db: Session, run_id: str, run_update: RunUpdate) -> Optional[Run]:
        """Update a run."""
        db_run = RunCRUD.get(db, run_id)
        if not db_run:
            return None
        
        update_data = run_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_run, field, value)
        
        db.commit()
        db.refresh(db_run)
        logger.info("Updated run", run_id=run_id, status=getattr(run_update, 'status', None))
        return db_run
    
    @staticmethod
    def get_latest_successful(db: Session, dataset_id: str) -> Optional[Run]:
        """Get the latest successful run for a dataset."""
        return (
            db.query(Run)
            .filter(Run.dataset_id == dataset_id, Run.status == RunStatus.COMPLETED)
            .order_by(Run.started_at.desc())
            .first()
        )


class ArtifactCRUD:
    """CRUD operations for artifacts."""
    
    @staticmethod
    def create(db: Session, artifact: ArtifactCreate) -> Artifact:
        """Create a new artifact."""
        db_artifact = Artifact(**artifact.dict())
        db.add(db_artifact)
        db.commit()
        db.refresh(db_artifact)
        logger.info("Created artifact", artifact_id=db_artifact.id, run_id=artifact.run_id, kind=artifact.kind)
        return db_artifact
    
    @staticmethod
    def get(db: Session, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID."""
        return db.query(Artifact).filter(Artifact.id == artifact_id).first()
    
    @staticmethod
    def list(db: Session, run_id: str) -> List[Artifact]:
        """List all artifacts for a run."""
        return db.query(Artifact).filter(Artifact.run_id == run_id).all()
    
    @staticmethod
    def get_by_kind(db: Session, run_id: str, kind: str) -> Optional[Artifact]:
        """Get artifact by run and kind."""
        return db.query(Artifact).filter(
            Artifact.run_id == run_id,
            Artifact.kind == kind
        ).first()


# Export CRUD classes for easy import
__all__ = [
    "engine",
    "SessionLocal", 
    "init_database",
    "get_database_session",
    "get_db_session",
    "get_session",
    "DatasetCRUD",
    "MappingCRUD", 
    "RunCRUD",
    "ArtifactCRUD",
]