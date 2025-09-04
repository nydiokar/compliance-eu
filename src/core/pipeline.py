import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from src.logging_conf import get_logger, log_data_processing_event
from src.core.intake import load_frame
from src.core.mapping import HeaderMatcher, load_profile
from src.core.normalize import normalize_dataframe, apply_column_mapping
from src.core.validate.rules import validate_dataframe
from src.core.outputs import export_to_open_data
from src.core.publish.ckan import create_ckan_client_from_settings, CKANPublisher, CKANError
from src.db import get_session, RunCRUD, ArtifactCRUD
from src.models import RunCreate, RunUpdate, ArtifactCreate, RunStatus, ArtifactKind
from src.settings import settings

logger = get_logger("pipeline")


class ProcessingPipeline:
    """Complete data processing pipeline from input to output."""
    
    def __init__(self, dataset_id: str, profile_name: str):
        self.dataset_id = dataset_id
        self.profile_name = profile_name
        self.profile = load_profile(profile_name)
        self.matcher = HeaderMatcher()
        self.run_id: Optional[str] = None
        
        if not self.profile:
            raise ValueError(f"Profile not found: {profile_name}")
    
    def process_file(
        self,
        file_path: Path,
        org_id: str,
        output_metadata: Optional[Dict[str, Any]] = None,
        publish_to_ckan: bool = False
    ) -> Dict[str, Any]:
        """Process a file through the complete pipeline.
        
        Returns:
            Dictionary with processing results and artifacts
        """
        logger.info("Starting file processing pipeline",
                   file=str(file_path),
                   dataset_id=self.dataset_id,
                   profile=self.profile_name)
        
        # Initialize run record
        run_id = self._start_run(file_path)
        
        try:
            # Stage 1: Load and parse file
            logger.info("Stage 1: Loading file")
            df_raw = load_frame(file_path)
            
            log_data_processing_event(
                self.dataset_id, run_id, "load", "completed",
                metrics={"rows": len(df_raw), "columns": len(df_raw.columns)}
            )
            
            # Stage 2: Header detection and mapping
            logger.info("Stage 2: Header mapping")
            mapping_result = self._map_headers(df_raw)
            base_df = mapping_result.get('reheadered_df', df_raw)
            df_mapped = apply_column_mapping(base_df, mapping_result['column_mapping'])
            
            log_data_processing_event(
                self.dataset_id, run_id, "mapping", "completed",
                metrics={
                    "matches_found": len(mapping_result['matches']),
                    "confidence": mapping_result['confidence']
                }
            )
            
            # Stage 3: Data normalization
            logger.info("Stage 3: Data normalization")
            df_normalized = normalize_dataframe(df_mapped, self.profile)

            # Stage 3.1: Validation
            logger.info("Stage 3.1: Validation")
            df_valid, df_errors = validate_dataframe(df_normalized, self.profile)
            
            # Calculate data quality metrics
            quality_metrics = self._calculate_quality_metrics(df_raw, df_valid)
            
            log_data_processing_event(
                self.dataset_id, run_id, "normalization", "completed",
                metrics=quality_metrics
            )
            
            # Stage 4: Export to Open Data format
            logger.info("Stage 4: Export to Open Data")
            export_metadata = self._prepare_export_metadata(output_metadata, mapping_result, quality_metrics)
            
            export_result = export_to_open_data(
                df_valid,
                export_metadata,
                f"dataset_{self.dataset_id}",
                org_id
            )
            
            log_data_processing_event(
                self.dataset_id, run_id, "export", "completed",
                output_hash=export_result['checksums']['csv']
            )
            
            # Stage 5: Save artifacts (including validation report if any)
            logger.info("Stage 5: Saving artifacts")
            # If validation errors exist, emit error CSV next to outputs
            if df_errors is not None and not df_errors.empty:
                error_csv_path = export_result['csv'].parent / (export_result['csv'].stem + "_errors.csv")
                df_errors.to_csv(error_csv_path, index=False, encoding='utf-8')
                export_result['validation_report'] = error_csv_path

            artifacts = self._save_artifacts(run_id, file_path, export_result, mapping_result)
            
            # Stage 6: Publish to CKAN (optional)
            ckan_result = None
            if publish_to_ckan:
                try:
                    ckan_result = self._publish_to_ckan(export_result, export_metadata, org_id, run_id)
                    logger.info("CKAN publishing completed", package_id=ckan_result.get('package_id'))
                except Exception as e:
                    logger.error("CKAN publishing failed", error=str(e))
                    # Don't fail the entire pipeline if CKAN publishing fails
            
            # Complete the run
            final_metrics = {
                "input_rows": len(df_raw),
                "output_rows": len(df_valid),
                "columns_mapped": len(mapping_result['matches']),
                "data_quality_score": quality_metrics.get('completeness', 0.0),
                "rows_invalid": int(len(df_raw) - len(df_valid))
            }
            
            # Update run with CKAN publication info if available
            if ckan_result:
                self._complete_run_with_ckan(run_id, export_result['checksums']['csv'], final_metrics, ckan_result)
            else:
                self._complete_run(run_id, export_result['checksums']['csv'], final_metrics)
            
            result = {
                'run_id': run_id,
                'status': 'completed',
                'input_stats': {
                    'rows': len(df_raw),
                    'columns': len(df_raw.columns)
                },
                'output_stats': {
                    'rows': len(df_normalized),
                    'columns': len(df_normalized.columns)
                },
                'mapping': mapping_result,
                'quality': quality_metrics,
                'exports': export_result,
                'artifacts': artifacts,
                'ckan_publication': ckan_result
            }
            
            logger.info("Pipeline processing completed successfully",
                       run_id=run_id,
                       input_rows=len(df_raw),
                       output_rows=len(df_normalized))
            
            return result
            
        except Exception as e:
            logger.error("Pipeline processing failed", error=str(e), run_id=run_id)
            if run_id:
                self._fail_run(run_id, str(e))
            raise
    
    def _start_run(self, file_path: Path) -> str:
        """Start a new processing run."""
        input_hash = self._calculate_file_hash(file_path)
        
        with get_session() as db:
            run_data = RunCreate(
                dataset_id=self.dataset_id,
                input_hash=input_hash
            )
            run = RunCRUD.create(db, run_data)
            self.run_id = run.id
            
            logger.info("Processing run started", run_id=run.id)
            return run.id
    
    def _map_headers(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Map input headers to profile fields."""
        # Use existing DataFrame columns as source headers by default
        source_headers = [str(c) for c in df.columns]
        header_row = -1
        detected_headers = source_headers.copy()

        # If columns look generic (e.g., Unnamed/Column_/#/empty), try to detect header row from data
        generic_markers = ("Unnamed:", "Column_")
        looks_generic = all(
            (not h) or h.startswith(generic_markers) or h.isdigit() for h in source_headers
        )
        reheadered_df = df
        if looks_generic:
            hdr_row, hdrs = self.matcher.detect_headers(df)
            if hdrs:
                header_row = hdr_row
                detected_headers = [str(h) for h in hdrs]
                try:
                    reheadered_df = df.iloc[header_row + 1 :].copy().reset_index(drop=True)
                    if len(detected_headers) == len(reheadered_df.columns):
                        reheadered_df.columns = detected_headers
                except Exception:
                    reheadered_df = df
        
        # Find best matches
        target_headers = list(self.profile.columns.keys())
        matches = self.matcher.find_best_matches(detected_headers, target_headers)
        
        # Create column mapping
        column_mapping = self.matcher.create_column_mapping(matches, self.profile.dict())
        
        # Calculate confidence
        confidence = len(matches) / len(target_headers) if target_headers else 0
        
        return {
            'header_row': header_row,
            'detected_headers': detected_headers,
            'matches': matches,
            'column_mapping': column_mapping,
            'confidence': confidence,
            'unmatched_sources': [h for h in detected_headers if h not in column_mapping],
            'unmatched_targets': [h for h in target_headers if h not in matches],
            'reheadered_df': reheadered_df
        }
    
    def _calculate_quality_metrics(self, df_input: pd.DataFrame, df_output: pd.DataFrame) -> Dict[str, float]:
        """Calculate data quality metrics."""
        input_cells = len(df_input) * len(df_input.columns)
        output_cells = len(df_output) * len(df_output.columns)
        
        input_nulls = df_input.isnull().sum().sum()
        output_nulls = df_output.isnull().sum().sum()
        
        metrics = {
            'input_completeness': float((input_cells - input_nulls) / input_cells) if input_cells > 0 else 0,
            'output_completeness': float((output_cells - output_nulls) / output_cells) if output_cells > 0 else 0,
            'row_retention_rate': float(len(df_output) / len(df_input)) if len(df_input) > 0 else 0,
            'column_mapping_rate': float(len(df_output.columns) / len(df_input.columns)) if len(df_input.columns) > 0 else 0
        }
        
        # Overall completeness score
        metrics['completeness'] = (metrics['output_completeness'] + metrics['row_retention_rate']) / 2
        
        return metrics
    
    def _prepare_export_metadata(
        self,
        base_metadata: Optional[Dict[str, Any]],
        mapping_result: Dict[str, Any],
        quality_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Prepare metadata for export."""
        metadata = base_metadata or {}
        
        # Add processing metadata
        metadata.update({
            'profile': self.profile_name,
            'processing_date': datetime.now().isoformat(),
            'mapping_confidence': mapping_result['confidence'],
            'quality_score': quality_metrics['completeness'],
            'validation_status': 'passed' if quality_metrics['completeness'] > 0.8 else 'warning'
        })
        
        return metadata
    
    def _save_artifacts(
        self,
        run_id: str,
        input_file: Path,
        export_result: Dict[str, Path],
        mapping_result: Dict[str, Any]
    ) -> Dict[str, str]:
        """Save processing artifacts to database."""
        artifacts = {}
        
        with get_session() as db:
            # Input file artifact
            input_artifact = ArtifactCreate(
                run_id=run_id,
                kind=ArtifactKind.INPUT_FILE,
                path=str(input_file.resolve()),
                checksum=self._calculate_file_hash(input_file),
                size_bytes=input_file.stat().st_size,
                mime_type=self._get_mime_type(input_file)
            )
            artifact = ArtifactCRUD.create(db, input_artifact)
            artifacts['input'] = artifact.id
            
            # Output CSV artifact
            csv_artifact = ArtifactCreate(
                run_id=run_id,
                kind=ArtifactKind.OUTPUT_CSV,
                path=str(export_result['csv'].resolve()),
                checksum=export_result['checksums']['csv'],
                size_bytes=export_result['csv'].stat().st_size,
                mime_type='text/csv'
            )
            artifact = ArtifactCRUD.create(db, csv_artifact)
            artifacts['csv'] = artifact.id
            
            # Output JSON artifact
            json_artifact = ArtifactCreate(
                run_id=run_id,
                kind=ArtifactKind.OUTPUT_JSON,
                path=str(export_result['json'].resolve()),
                checksum=export_result['checksums']['json'],
                size_bytes=export_result['json'].stat().st_size,
                mime_type='application/json'
            )
            artifact = ArtifactCRUD.create(db, json_artifact)
            artifacts['json'] = artifact.id
            
            # Metadata artifact
            metadata_artifact = ArtifactCreate(
                run_id=run_id,
                kind=ArtifactKind.METADATA,
                path=str(export_result['metadata'].resolve()),
                checksum=self._calculate_file_hash(export_result['metadata']),
                size_bytes=export_result['metadata'].stat().st_size,
                mime_type='application/json'
            )
            artifact = ArtifactCRUD.create(db, metadata_artifact)
            artifacts['metadata'] = artifact.id

            # Validation report artifact (optional)
            if 'validation_report' in export_result:
                val_path = export_result['validation_report']
                val_art = ArtifactCreate(
                    run_id=run_id,
                    kind=ArtifactKind.VALIDATION_REPORT,
                    path=str(val_path.resolve()),
                    checksum=self._calculate_file_hash(val_path),
                    size_bytes=val_path.stat().st_size,
                    mime_type='text/csv'
                )
                artifact = ArtifactCRUD.create(db, val_art)
                artifacts['validation_report'] = artifact.id
        
        return artifacts
    
    def _complete_run(self, run_id: str, output_hash: str, metrics: Dict[str, Any]):
        """Complete the processing run."""
        with get_session() as db:
            update_data = RunUpdate(
                status=RunStatus.COMPLETED,
                finished_at=datetime.now(),
                output_hash=output_hash,
                rows_processed=metrics.get('input_rows', 0),
                rows_valid=metrics.get('output_rows', 0),
                rows_invalid=metrics.get('input_rows', 0) - metrics.get('output_rows', 0),
                message="Processing completed successfully"
            )
            RunCRUD.update(db, run_id, update_data)
    
    def _fail_run(self, run_id: str, error_message: str):
        """Mark the run as failed."""
        with get_session() as db:
            update_data = RunUpdate(
                status=RunStatus.FAILED,
                finished_at=datetime.now(),
                message=error_message
            )
            RunCRUD.update(db, run_id, update_data)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type based on file extension."""
        extension = file_path.suffix.lower()
        mime_types = {
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.json': 'application/json',
            '.pdf': 'application/pdf'
        }
        return mime_types.get(extension, 'application/octet-stream')
    
    def _publish_to_ckan(
        self,
        export_result: Dict[str, Path],
        metadata: Dict[str, Any],
        org_id: str,
        run_id: str
    ) -> Dict[str, Any]:
        """Publish dataset to CKAN."""
        logger.info("Starting CKAN publication", dataset_id=self.dataset_id)
        
        # Create CKAN client
        try:
            client = create_ckan_client_from_settings()
            publisher = CKANPublisher(client)
        except CKANError as e:
            logger.error("Failed to create CKAN client", error=str(e))
            raise
        
        # Test connection first
        if not client.test_connection():
            raise CKANError("Cannot connect to CKAN instance")
        
        # Publish dataset
        result = publisher.publish_dataset(
            dataset_metadata=metadata,
            csv_file=export_result['csv'],
            json_file=export_result['json'],
            metadata_file=export_result['metadata'],
            org_id=settings.ckan_organization or org_id,
            dataset_id=self.dataset_id
        )
        
        # Log publication event
        log_data_processing_event(
            self.dataset_id, run_id, "ckan_publish", "completed",
            package_id=result['package_id'],
            ckan_url=result['url']
        )
        
        return result
    
    def _complete_run_with_ckan(
        self,
        run_id: str,
        output_hash: str,
        metrics: Dict[str, Any],
        ckan_result: Dict[str, Any]
    ):
        """Complete the processing run with CKAN publication info."""
        with get_session() as db:
            update_data = RunUpdate(
                status=RunStatus.COMPLETED,
                finished_at=datetime.now(),
                output_hash=output_hash,
                rows_processed=metrics.get('input_rows', 0),
                rows_valid=metrics.get('output_rows', 0),
                rows_invalid=metrics.get('input_rows', 0) - metrics.get('output_rows', 0),
                external_package_id=ckan_result.get('package_id'),
                external_resource_id=ckan_result.get('resources', {}).get('csv', {}).get('id'),
                message="Processing and CKAN publication completed successfully"
            )
            RunCRUD.update(db, run_id, update_data)


def process_file_pipeline(
    file_path: Path,
    dataset_id: str,
    profile_name: str,
    org_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    publish_to_ckan: bool = False
) -> Dict[str, Any]:
    """Convenience function to process a file through the complete pipeline."""
    pipeline = ProcessingPipeline(dataset_id, profile_name)
    return pipeline.process_file(file_path, org_id, metadata, publish_to_ckan)
