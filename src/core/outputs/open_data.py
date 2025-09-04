import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger("open_data")


class OpenDataExporter:
    """Export data to Open Data formats (CSV/JSON + metadata)."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export(
        self,
        df: pd.DataFrame,
        metadata: Dict[str, Any],
        dataset_name: str,
        org_id: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Path]:
        """Export DataFrame to Open Data format with metadata.
        
        Returns:
            Dict with paths to created files
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        logger.info("Starting Open Data export", 
                   dataset=dataset_name, 
                   org=org_id,
                   rows=len(df),
                   columns=len(df.columns))
        
        # Generate filenames
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        base_filename = f"{dataset_name}_{org_id}_{timestamp_str}"
        
        # Create output directory for this dataset
        dataset_dir = self.output_dir / org_id / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # Export CSV
        csv_path = dataset_dir / f"{base_filename}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8')
        logger.debug(f"CSV exported to {csv_path}")
        
        # Export JSON
        json_path = dataset_dir / f"{base_filename}.json"
        df.to_json(json_path, orient='records', indent=2, force_ascii=False)
        logger.debug(f"JSON exported to {json_path}")
        
        # Calculate file checksums
        csv_checksum = self._calculate_checksum(csv_path)
        json_checksum = self._calculate_checksum(json_path)
        
        # Create enhanced metadata
        enhanced_metadata = self._create_metadata(
            df, metadata, dataset_name, org_id, timestamp,
            csv_path, json_path, csv_checksum, json_checksum
        )
        
        # Export metadata
        metadata_path = dataset_dir / f"{base_filename}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False, default=str)
        logger.debug(f"Metadata exported to {metadata_path}")
        
        # Create package ZIP (optional)
        zip_path = None
        if metadata.get('create_package', False):
            zip_path = self._create_package(
                dataset_dir, base_filename,
                [csv_path, json_path, metadata_path]
            )
        
        result = {
            'csv': csv_path,
            'json': json_path,
            'metadata': metadata_path,
            'checksums': {
                'csv': csv_checksum,
                'json': json_checksum
            }
        }
        
        if zip_path:
            result['package'] = zip_path
        
        logger.info("Open Data export completed successfully", 
                   csv_size=csv_path.stat().st_size,
                   json_size=json_path.stat().st_size)
        
        return result


def export_to_open_data(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    dataset_name: str,
    org_id: str,
    output_dir: Optional[Path] = None,
):
    """Convenience wrapper to export a DataFrame to Open Data outputs.

    Returns dict with paths to created files.
    """
    exporter = OpenDataExporter(output_dir=output_dir)
    return exporter.export(df, metadata, dataset_name, org_id)
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _create_metadata(
        self,
        df: pd.DataFrame,
        base_metadata: Dict[str, Any],
        dataset_name: str,
        org_id: str,
        timestamp: datetime,
        csv_path: Path,
        json_path: Path,
        csv_checksum: str,
        json_checksum: str
    ) -> Dict[str, Any]:
        """Create comprehensive metadata."""
        
        # Basic dataset info
        metadata = {
            'title': base_metadata.get('title', f'{dataset_name} - {org_id}'),
            'description': base_metadata.get('description', ''),
            'publisher': base_metadata.get('publisher', org_id),
            'license': base_metadata.get('license', 'Open Data License'),
            'update_frequency': base_metadata.get('update_frequency', 'monthly'),
            'created': timestamp.isoformat(),
            'modified': timestamp.isoformat(),
            'temporal_coverage': base_metadata.get('temporal_coverage', ''),
            'spatial_coverage': base_metadata.get('spatial_coverage', ''),
            'keywords': base_metadata.get('keywords', [dataset_name]),
            'contact': base_metadata.get('contact', {}),
        }
        
        # Data characteristics
        metadata['data'] = {
            'format': 'CSV/JSON',
            'encoding': 'UTF-8',
            'column_count': len(df.columns),
            'row_count': len(df),
            'columns': list(df.columns),
            'data_types': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'null_counts': df.isnull().sum().to_dict(),
            'memory_usage': df.memory_usage(deep=True).sum()
        }
        
        # File information
        metadata['files'] = {
            'csv': {
                'path': csv_path.name,
                'size_bytes': csv_path.stat().st_size,
                'checksum': csv_checksum,
                'mime_type': 'text/csv'
            },
            'json': {
                'path': json_path.name,
                'size_bytes': json_path.stat().st_size,
                'checksum': json_checksum,
                'mime_type': 'application/json'
            }
        }
        
        # Processing information
        metadata['processing'] = {
            'generated_by': 'Compliance Automation Kit',
            'version': settings.app_version,
            'processing_date': timestamp.isoformat(),
            'profile_used': base_metadata.get('profile', ''),
            'validation_status': base_metadata.get('validation_status', 'unknown')
        }
        
        # Statistical summary for numeric columns
        numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_columns) > 0:
            metadata['statistics'] = {
                col: {
                    'count': int(df[col].count()),
                    'mean': float(df[col].mean()) if df[col].count() > 0 else None,
                    'std': float(df[col].std()) if df[col].count() > 1 else None,
                    'min': float(df[col].min()) if df[col].count() > 0 else None,
                    'max': float(df[col].max()) if df[col].count() > 0 else None
                }
                for col in numeric_columns
            }
        
        # Quality indicators
        total_cells = len(df) * len(df.columns)
        null_cells = df.isnull().sum().sum()
        metadata['quality'] = {
            'completeness': float((total_cells - null_cells) / total_cells) if total_cells > 0 else 0,
            'total_cells': total_cells,
            'null_cells': int(null_cells),
            'duplicate_rows': int(df.duplicated().sum())
        }
        
        return metadata
    
    def _create_package(
        self,
        base_dir: Path,
        base_filename: str,
        files: list
    ) -> Path:
        """Create a ZIP package with all files."""
        import zipfile
        
        zip_path = base_dir / f"{base_filename}_package.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                zipf.write(file_path, file_path.name)
        
        logger.debug(f"Package created at {zip_path}")
        return zip_path


def export_to_open_data(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    dataset_name: str,
    org_id: str,
    output_dir: Optional[Path] = None
) -> Dict[str, Path]:
    """Convenience function to export data to Open Data format."""
    exporter = OpenDataExporter(output_dir)
    return exporter.export(df, metadata, dataset_name, org_id)
