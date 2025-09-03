#!/usr/bin/env python3
"""
End-to-end test for the Compliance Kit pipeline
Tests: XLSX → canonical CSV/JSON + metadata with audit record
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.settings import settings
from src.logging_conf import setup_logging, get_logger
from src.db import init_database, get_session, DatasetCRUD
from src.models import DatasetCreate
from src.core.pipeline import process_file_pipeline

# Initialize
logger = setup_logging()


def test_end_to_end():
    """Run complete end-to-end test."""
    logger.info("Starting end-to-end test")
    
    try:
        # Initialize database
        init_database()
        logger.info("Database initialized")
        
        # Create test dataset
        test_org_id = "test_municipality"
        test_dataset_name = "budget_execution_test"
        
        dataset_data = DatasetCreate(
            org_id=test_org_id,
            name=test_dataset_name,
            profile="budget_execution_v1",
            description="End-to-end test dataset",
            publish_target="none"
        )
        
        with get_session() as db:
            # Check if dataset already exists
            existing = DatasetCRUD.get_by_name(db, test_org_id, test_dataset_name)
            if existing:
                dataset = existing
                logger.info(f"Using existing dataset: {dataset.id}")
            else:
                dataset = DatasetCRUD.create(db, dataset_data)
                logger.info(f"Created test dataset: {dataset.id}")
        
        # Test file path
        test_file = Path("tests/data_fixtures/budget_sample_en.csv")
        if not test_file.exists():
            logger.error(f"Test file not found: {test_file}")
            return False
        
        # Prepare metadata
        test_metadata = {
            "title": "Municipal Budget Execution - E2E Test",
            "description": "End-to-end test of budget execution data processing",
            "publisher": test_org_id,
            "temporal_coverage": "2025-01",
            "keywords": ["budget", "test", "municipal"],
            "contact": {
                "name": "Test Administrator",
                "email": "test@example.com"
            }
        }
        
        # Run the complete pipeline
        logger.info("Starting pipeline processing")
        start_time = datetime.now()
        
        result = process_file_pipeline(
            file_path=test_file,
            dataset_id=dataset.id,
            profile_name="budget_execution_v1",
            org_id=test_org_id,
            metadata=test_metadata
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("Pipeline processing completed", 
                   duration_seconds=duration,
                   run_id=result['run_id'])
        
        # Validate results
        success = validate_results(result, test_file)
        
        if success:
            logger.info("🎉 End-to-end test PASSED!")
            print_results_summary(result, duration)
            return True
        else:
            logger.error("❌ End-to-end test FAILED!")
            return False
            
    except Exception as e:
        logger.error("End-to-end test failed with exception", error=str(e))
        import traceback
        traceback.print_exc()
        return False


def validate_results(result: dict, input_file: Path) -> bool:
    """Validate the processing results."""
    logger.info("Validating results")
    
    try:
        # Check that all expected keys are present
        required_keys = ['run_id', 'status', 'input_stats', 'output_stats', 
                        'mapping', 'quality', 'exports', 'artifacts']
        
        for key in required_keys:
            if key not in result:
                logger.error(f"Missing result key: {key}")
                return False
        
        # Check status
        if result['status'] != 'completed':
            logger.error(f"Expected status 'completed', got '{result['status']}'")
            return False
        
        # Check that files were created
        exports = result['exports']
        for file_type in ['csv', 'json', 'metadata']:
            if file_type not in exports:
                logger.error(f"Missing export file type: {file_type}")
                return False
            
            file_path = exports[file_type]
            if not file_path.exists():
                logger.error(f"Export file does not exist: {file_path}")
                return False
            
            if file_path.stat().st_size == 0:
                logger.error(f"Export file is empty: {file_path}")
                return False
        
        # Check data integrity
        import pandas as pd
        
        # Read original file
        df_original = pd.read_csv(input_file)
        
        # Read processed CSV
        df_processed = pd.read_csv(exports['csv'])
        
        # Basic data checks
        if len(df_processed) == 0:
            logger.error("Processed data is empty")
            return False
        
        if len(df_processed) != len(df_original):
            logger.warning(f"Row count changed: {len(df_original)} → {len(df_processed)}")
        
        # Check mapping quality
        mapping_confidence = result['mapping']['confidence']
        if mapping_confidence < 0.5:
            logger.warning(f"Low mapping confidence: {mapping_confidence:.2%}")
        
        # Check data quality
        quality_score = result['quality']['completeness']
        if quality_score < 0.8:
            logger.warning(f"Low data quality score: {quality_score:.2%}")
        
        # Validate metadata JSON
        metadata_path = exports['metadata']
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        required_metadata_keys = ['title', 'description', 'created', 'data', 'files', 'quality']
        for key in required_metadata_keys:
            if key not in metadata:
                logger.error(f"Missing metadata key: {key}")
                return False
        
        # Validate checksums
        checksums = result['exports']['checksums']
        if not checksums.get('csv') or not checksums.get('json'):
            logger.error("Missing file checksums")
            return False
        
        logger.info("All validation checks passed")
        return True
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False


def print_results_summary(result: dict, duration: float):
    """Print a summary of the test results."""
    print("\n" + "="*60)
    print("🎉 END-TO-END TEST RESULTS")
    print("="*60)
    
    print(f"Run ID: {result['run_id']}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Status: {result['status'].upper()}")
    
    print("\nInput Statistics:")
    input_stats = result['input_stats']
    print(f"  Rows: {input_stats['rows']}")
    print(f"  Columns: {input_stats['columns']}")
    
    print("\nOutput Statistics:")
    output_stats = result['output_stats']
    print(f"  Rows: {output_stats['rows']}")
    print(f"  Columns: {output_stats['columns']}")
    
    print("\nMapping Results:")
    mapping = result['mapping']
    print(f"  Confidence: {mapping['confidence']:.2%}")
    print(f"  Matches found: {len(mapping['matches'])}")
    print(f"  Unmatched sources: {len(mapping['unmatched_sources'])}")
    print(f"  Unmatched targets: {len(mapping['unmatched_targets'])}")
    
    print("\nData Quality:")
    quality = result['quality']
    print(f"  Completeness: {quality['completeness']:.2%}")
    print(f"  Row retention: {quality['row_retention_rate']:.2%}")
    print(f"  Column mapping: {quality['column_mapping_rate']:.2%}")
    
    print("\nGenerated Files:")
    exports = result['exports']
    for file_type, file_path in exports.items():
        if isinstance(file_path, Path) and file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print(f"  {file_type.upper()}: {file_path.name} ({size_kb:.1f} KB)")
    
    print("\nArtifacts Created:")
    artifacts = result['artifacts']
    for artifact_type, artifact_id in artifacts.items():
        print(f"  {artifact_type}: {artifact_id}")
    
    print("\n✅ All tests passed successfully!")
    print("="*60)


if __name__ == '__main__':
    success = test_end_to_end()
    sys.exit(0 if success else 1)