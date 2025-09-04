"""Dataset processing job functions for the scheduler."""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from src.logging_conf import get_logger
from src.core.pipeline import process_file_pipeline
from src.db import get_session, DatasetCRUD
from src.models import Dataset
from src.settings import settings

logger = get_logger("scheduler.jobs")


def process_dataset_job(dataset_id: str, **kwargs) -> Dict[str, Any]:
    """Process a dataset as a scheduled job.
    
    This function is designed to be called by the scheduler for automated
    dataset processing.
    
    Args:
        dataset_id: ID of dataset to process
        **kwargs: Additional job parameters
        
    Returns:
        Job execution result
    """
    logger.info("Starting scheduled dataset processing", dataset_id=dataset_id)
    
    try:
        # Get dataset configuration
        with get_session() as db:
            dataset = DatasetCRUD.get(db, dataset_id)
            if not dataset:
                raise ValueError(f"Dataset not found: {dataset_id}")
            
            if not dataset.active:
                logger.info("Dataset is inactive, skipping", dataset_id=dataset_id)
                return {
                    "status": "skipped",
                    "reason": "dataset_inactive",
                    "dataset_id": dataset_id
                }
        
        # Look for input files in upload directory
        upload_path = settings.upload_dir / dataset.org_id / dataset_id
        if not upload_path.exists():
            logger.warning("No upload directory found", path=str(upload_path))
            return {
                "status": "skipped", 
                "reason": "no_upload_directory",
                "dataset_id": dataset_id
            }
        
        # Find the most recent input file
        input_file = find_latest_input_file(upload_path)
        if not input_file:
            logger.info("No input files found", path=str(upload_path))
            return {
                "status": "skipped",
                "reason": "no_input_files",
                "dataset_id": dataset_id
            }
        
        logger.info("Processing input file", file=str(input_file), dataset_id=dataset_id)
        
        # Prepare metadata
        metadata = {
            "title": dataset.name,
            "description": dataset.description or f"Automated processing of {dataset.name}",
            "profile": dataset.profile,
            "scheduled": True,
            "dataset_id": dataset_id,
            "org_id": dataset.org_id
        }
        
        # Determine if CKAN publishing should be enabled
        publish_to_ckan = (
            dataset.publish_target == "ckan" and 
            settings.ckan_url is not None and 
            settings.ckan_api_key is not None
        )
        
        logger.info("Starting pipeline processing", 
                   publish_to_ckan=publish_to_ckan,
                   profile=dataset.profile)
        
        # Process through pipeline
        result = process_file_pipeline(
            file_path=input_file,
            dataset_id=dataset_id,
            profile_name=dataset.profile,
            org_id=dataset.org_id,
            metadata=metadata,
            publish_to_ckan=publish_to_ckan
        )
        
        # Prepare job result
        job_result = {
            "status": "completed",
            "dataset_id": dataset_id,
            "run_id": result["run_id"],
            "input_file": str(input_file),
            "input_rows": result["input_stats"]["rows"],
            "output_rows": result["output_stats"]["rows"],
            "data_quality_score": result["quality"].get("completeness", 0),
            "exports": {
                "csv": str(result["exports"]["csv"]),
                "json": str(result["exports"]["json"]),
                "metadata": str(result["exports"]["metadata"])
            }
        }
        
        # Add CKAN publication info if available
        if result.get("ckan_publication"):
            ckan_info = result["ckan_publication"]
            job_result["ckan_publication"] = {
                "package_id": ckan_info.get("package_id"),
                "package_name": ckan_info.get("package_name"),
                "url": ckan_info.get("url"),
                "resources_count": len(ckan_info.get("resources", {}))
            }
        
        logger.info("Scheduled dataset processing completed successfully",
                   dataset_id=dataset_id,
                   run_id=result["run_id"],
                   input_rows=job_result["input_rows"],
                   output_rows=job_result["output_rows"])
        
        return job_result
        
    except Exception as e:
        logger.error("Scheduled dataset processing failed",
                    dataset_id=dataset_id,
                    error=str(e))
        
        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "error": str(e),
            "error_type": type(e).__name__
        }


def find_latest_input_file(upload_path: Path) -> Optional[Path]:
    """Find the most recent input file in upload directory.
    
    Args:
        upload_path: Path to upload directory
        
    Returns:
        Path to most recent file or None
    """
    allowed_extensions = {'.csv', '.xlsx', '.xls'}
    
    try:
        input_files = []
        for file_path in upload_path.iterdir():
            if (file_path.is_file() and 
                file_path.suffix.lower() in allowed_extensions):
                input_files.append(file_path)
        
        if not input_files:
            return None
        
        # Return most recently modified file
        return max(input_files, key=lambda f: f.stat().st_mtime)
        
    except Exception as e:
        logger.error("Error finding input files", path=str(upload_path), error=str(e))
        return None


def setup_dataset_schedule(dataset: Dataset, scheduler) -> str:
    """Set up scheduled processing for a dataset.
    
    Args:
        dataset: Dataset configuration
        scheduler: JobScheduler instance
        
    Returns:
        Job ID
    """
    if not dataset.schedule_cron:
        raise ValueError(f"Dataset {dataset.id} has no cron schedule")
    
    job_id = f"dataset_{dataset.id}"
    
    # Remove existing job if it exists
    scheduler.remove_job(job_id)
    
    # Add new job
    scheduler.add_job(
        name=f"Process dataset: {dataset.name}",
        cron_expression=dataset.schedule_cron,
        function=process_dataset_job,
        kwargs={"dataset_id": dataset.id},
        job_id=job_id,
        enabled=dataset.active
    )
    
    logger.info("Dataset schedule configured",
               dataset_id=dataset.id,
               cron=dataset.schedule_cron,
               job_id=job_id)
    
    return job_id


def remove_dataset_schedule(dataset_id: str, scheduler) -> bool:
    """Remove scheduled processing for a dataset.
    
    Args:
        dataset_id: Dataset ID
        scheduler: JobScheduler instance
        
    Returns:
        True if schedule was removed
    """
    job_id = f"dataset_{dataset_id}"
    return scheduler.remove_job(job_id)


def update_dataset_schedule(dataset: Dataset, scheduler) -> str:
    """Update scheduled processing for a dataset.
    
    Args:
        dataset: Updated dataset configuration
        scheduler: JobScheduler instance
        
    Returns:
        Job ID
    """
    job_id = f"dataset_{dataset.id}"
    
    if not dataset.schedule_cron:
        # Remove schedule if no cron expression
        scheduler.remove_job(job_id)
        return job_id
    
    # Check if job exists
    existing_job = scheduler.get_job(job_id)
    
    if existing_job:
        # Update existing job
        scheduler.update_job_schedule(job_id, dataset.schedule_cron)
        
        if dataset.active:
            scheduler.enable_job(job_id)
        else:
            scheduler.disable_job(job_id)
    else:
        # Create new job
        setup_dataset_schedule(dataset, scheduler)
    
    return job_id