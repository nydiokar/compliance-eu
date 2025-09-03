#!/usr/bin/env python3
"""
Compliance Kit CLI - Command line interface for EU Compliance Automation Kit
"""

import sys
import json
import click
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.settings import settings
from src.logging_conf import setup_logging, get_logger
from src.db import init_database, get_session, DatasetCRUD, RunCRUD, MappingCRUD
from src.models import DatasetCreate, RunCreate, MappingCreate, RunStatus
from src.core.intake import load_frame
from src.core.mapping import load_profile, list_profiles
from src.core.normalize import normalize_dataframe, apply_column_mapping

# Initialize logging for CLI
logger = setup_logging()


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--config', type=click.Path(exists=True), help='Config file path')
@click.pass_context
def cli(ctx, debug, config):
    """Compliance Kit - EU Compliance Automation CLI"""
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug
    
    if debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Initialize database
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)


@cli.group()
def dataset():
    """Dataset management commands"""
    pass


@dataset.command('list')
@click.option('--org-id', help='Filter by organization ID')
@click.option('--active/--inactive', default=True, help='Show active/inactive datasets')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table')
def list_datasets(org_id, active, output_format):
    """List datasets"""
    with get_session() as db:
        datasets = DatasetCRUD.list(db, org_id=org_id, active_only=active, limit=100)
        
        if output_format == 'json':
            data = [{'id': d.id, 'name': d.name, 'org_id': d.org_id, 'profile': d.profile,
                    'active': d.active, 'created_at': d.created_at.isoformat()} for d in datasets]
            click.echo(json.dumps(data, indent=2))
        else:
            if not datasets:
                click.echo("No datasets found")
                return
            
            click.echo(f"{'ID':<36} {'Name':<25} {'Org ID':<15} {'Profile':<20} {'Status':<8} {'Created'}")
            click.echo("-" * 110)
            for d in datasets:
                status = "Active" if d.active else "Inactive"
                created = d.created_at.strftime("%Y-%m-%d")
                click.echo(f"{d.id:<36} {d.name:<25} {d.org_id:<15} {d.profile:<20} {status:<8} {created}")


@dataset.command('create')
@click.option('--org-id', required=True, help='Organization ID')
@click.option('--name', required=True, help='Dataset name')
@click.option('--profile', required=True, help='Profile name')
@click.option('--description', help='Dataset description')
@click.option('--schedule', help='Cron schedule')
@click.option('--publish-target', type=click.Choice(['none', 'ckan', 'ftp']), default='none')
def create_dataset(org_id, name, profile, description, schedule, publish_target):
    """Create a new dataset"""
    dataset_data = DatasetCreate(
        org_id=org_id,
        name=name,
        profile=profile,
        description=description,
        schedule_cron=schedule,
        publish_target=publish_target
    )
    
    try:
        with get_session() as db:
            dataset = DatasetCRUD.create(db, dataset_data)
            click.echo(f"Dataset created: {dataset.id}")
            click.echo(f"Name: {dataset.name}")
            click.echo(f"Profile: {dataset.profile}")
    except Exception as e:
        click.echo(f"Error creating dataset: {e}", err=True)
        sys.exit(1)


@dataset.command('show')
@click.argument('dataset_id')
def show_dataset(dataset_id):
    """Show dataset details"""
    with get_session() as db:
        dataset = DatasetCRUD.get(db, dataset_id)
        if not dataset:
            click.echo(f"Dataset not found: {dataset_id}", err=True)
            sys.exit(1)
        
        click.echo(f"ID: {dataset.id}")
        click.echo(f"Name: {dataset.name}")
        click.echo(f"Organization: {dataset.org_id}")
        click.echo(f"Profile: {dataset.profile}")
        click.echo(f"Description: {dataset.description or 'N/A'}")
        click.echo(f"Schedule: {dataset.schedule_cron or 'Manual'}")
        click.echo(f"Publish Target: {dataset.publish_target}")
        click.echo(f"Status: {'Active' if dataset.active else 'Inactive'}")
        click.echo(f"Created: {dataset.created_at}")
        click.echo(f"Updated: {dataset.updated_at}")


@dataset.command('delete')
@click.argument('dataset_id')
@click.confirmation_option(prompt='Are you sure you want to delete this dataset?')
def delete_dataset(dataset_id):
    """Delete a dataset"""
    with get_session() as db:
        success = DatasetCRUD.delete(db, dataset_id)
        if success:
            click.echo(f"Dataset deleted: {dataset_id}")
        else:
            click.echo(f"Dataset not found: {dataset_id}", err=True)
            sys.exit(1)


@cli.group()
def profile():
    """Profile management commands"""
    pass


@profile.command('list')
def list_profiles_cmd():
    """List available profiles"""
    profiles = list_profiles()
    
    if not profiles:
        click.echo("No profiles found")
        return
    
    click.echo("Available profiles:")
    for p in profiles:
        click.echo(f"  - {p}")


@profile.command('show')
@click.argument('profile_name')
def show_profile(profile_name):
    """Show profile details"""
    profile_obj = load_profile(profile_name)
    if not profile_obj:
        click.echo(f"Profile not found: {profile_name}", err=True)
        sys.exit(1)
    
    click.echo(f"Profile: {profile_obj.profile}")
    click.echo(f"Version: {profile_obj.version}")
    click.echo(f"Description: {profile_obj.description or 'N/A'}")
    click.echo(f"Created: {profile_obj.created_at or 'N/A'}")
    click.echo(f"Created by: {profile_obj.created_by or 'N/A'}")
    click.echo(f"Tags: {', '.join(profile_obj.tags) if profile_obj.tags else 'None'}")
    
    click.echo("\nColumns:")
    for col_name, col_spec in profile_obj.columns.items():
        click.echo(f"  {col_name}:")
        click.echo(f"    Type: {col_spec.type}")
        click.echo(f"    Sources: {col_spec.sources}")
        click.echo(f"    Required: {col_spec.required}")
        if col_spec.description:
            click.echo(f"    Description: {col_spec.description}")


@cli.group()
def run():
    """Run management commands"""
    pass


@run.command('list')
@click.option('--dataset-id', help='Filter by dataset ID')
@click.option('--status', type=click.Choice([s.value for s in RunStatus]), help='Filter by status')
@click.option('--limit', type=int, default=20, help='Number of runs to show')
def list_runs(dataset_id, status, limit):
    """List runs"""
    with get_session() as db:
        status_enum = RunStatus(status) if status else None
        runs = RunCRUD.list(db, dataset_id=dataset_id, status=status_enum, limit=limit)
        
        if not runs:
            click.echo("No runs found")
            return
        
        click.echo(f"{'ID':<36} {'Dataset':<36} {'Status':<12} {'Started':<16} {'Duration'}")
        click.echo("-" * 120)
        
        for r in runs:
            duration = "N/A"
            if r.finished_at:
                delta = r.finished_at - r.started_at
                duration = str(delta).split('.')[0]  # Remove microseconds
            
            click.echo(f"{r.id:<36} {r.dataset_id:<36} {r.status.value:<12} "
                      f"{r.started_at.strftime('%Y-%m-%d %H:%M'):<16} {duration}")


@run.command('show')
@click.argument('run_id')
def show_run(run_id):
    """Show run details"""
    with get_session() as db:
        run = RunCRUD.get(db, run_id)
        if not run:
            click.echo(f"Run not found: {run_id}", err=True)
            sys.exit(1)
        
        click.echo(f"ID: {run.id}")
        click.echo(f"Dataset ID: {run.dataset_id}")
        click.echo(f"Status: {run.status.value}")
        click.echo(f"Started: {run.started_at}")
        click.echo(f"Finished: {run.finished_at or 'N/A'}")
        click.echo(f"Input Hash: {run.input_hash or 'N/A'}")
        click.echo(f"Output Hash: {run.output_hash or 'N/A'}")
        click.echo(f"Rows Processed: {run.rows_processed or 'N/A'}")
        click.echo(f"Rows Valid: {run.rows_valid or 'N/A'}")
        click.echo(f"Rows Invalid: {run.rows_invalid or 'N/A'}")
        click.echo(f"Message: {run.message or 'N/A'}")
        
        if run.external_package_id:
            click.echo(f"External Package ID: {run.external_package_id}")
        if run.external_resource_id:
            click.echo(f"External Resource ID: {run.external_resource_id}")


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--dataset-id', required=True, help='Dataset ID to use (provides org/profile)')
def process(file_path, dataset_id):
    """Process a file end-to-end using the configured dataset profile."""
    from src.db import get_session, DatasetCRUD
    from src.core.pipeline import process_file_pipeline

    file_path = Path(file_path)
    try:
        with get_session() as db:
            dataset = DatasetCRUD.get(db, dataset_id)
            if not dataset:
                click.echo(f"Dataset not found: {dataset_id}", err=True)
                sys.exit(1)

            click.echo(f"Processing {file_path} with profile '{dataset.profile}' for org '{dataset.org_id}'")
            result = process_file_pipeline(
                file_path=file_path,
                dataset_id=dataset_id,
                profile_name=dataset.profile,
                org_id=dataset.org_id,
                metadata={
                    "title": dataset.name,
                    "publisher": dataset.org_id,
                    "profile": dataset.profile,
                }
            )

            exports = result.get('exports', {})
            click.echo("\nCompleted. Outputs:")
            for k in ('csv', 'json', 'metadata'):
                p = exports.get(k)
                if p:
                    click.echo(f"  {k}: {p}")
            if 'validation_report' in exports:
                click.echo(f"  validation_report: {exports['validation_report']}")
            click.echo(f"Run ID: {result.get('run_id')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--profile', help='Profile to suggest mappings for')
def analyze(file_path, profile):
    """Analyze a file and suggest mappings"""
    file_path = Path(file_path)
    
    try:
        # Load file
        click.echo(f"Analyzing file: {file_path}")
        df = load_frame(file_path)
        
        # Basic file info
        click.echo(f"\nFile Statistics:")
        click.echo(f"  Rows: {len(df)}")
        click.echo(f"  Columns: {len(df.columns)}")
        click.echo(f"  Size: {file_path.stat().st_size / 1024:.1f} KB")
        
        # Show detected headers
        from src.core.mapping import detect_headers
        header_row, headers = detect_headers(df)
        
        click.echo(f"\nDetected Headers (row {header_row}):")
        for i, header in enumerate(headers):
            click.echo(f"  {i+1}: {header}")
        
        # Show data types
        click.echo(f"\nData Types:")
        for col in df.columns:
            dtype = df[col].dtype
            non_null = df[col].count()
            click.echo(f"  {col}: {dtype} ({non_null}/{len(df)} non-null)")
        
        # Show sample data
        click.echo(f"\nSample Data (first 3 rows):")
        click.echo(df.head(3).to_string())
        
        # Suggest mappings if profile provided
        if profile:
            profile_obj = load_profile(profile)
            if profile_obj:
                from src.core.mapping import HeaderMatcher
                matcher = HeaderMatcher()
                suggestions = matcher.suggest_mappings(df, profile_obj.dict())
                
                click.echo(f"\nMapping Suggestions for profile '{profile}':")
                click.echo(f"Confidence: {suggestions['confidence']:.2%}")
                
                if suggestions['matches']:
                    click.echo("\nMatches found:")
                    for target, (source, similarity) in suggestions['matches'].items():
                        click.echo(f"  {target} <- {source} (similarity: {similarity:.2f})")
                
                if suggestions['unmatched_sources']:
                    click.echo("\nUnmatched source columns:")
                    for col in suggestions['unmatched_sources']:
                        click.echo(f"  - {col}")
                
                if suggestions['unmatched_targets']:
                    click.echo("\nMissing target columns:")
                    for col in suggestions['unmatched_targets']:
                        click.echo(f"  - {col}")
    
    except Exception as e:
        click.echo(f"Error analyzing file: {e}", err=True)
        sys.exit(1)


@cli.command()
def info():
    """Show system information"""
    click.echo(f"Compliance Kit v{settings.app_version}")
    click.echo(f"Settings file: {settings.__class__.__module__}")
    click.echo(f"Database URL: {settings.database_url}")
    click.echo(f"Data directory: {settings.data_dir}")
    click.echo(f"Upload directory: {settings.upload_dir}")
    click.echo(f"Output directory: {settings.output_dir}")
    click.echo(f"Debug mode: {settings.debug}")
    
    # Show available profiles
    profiles = list_profiles()
    click.echo(f"Available profiles: {len(profiles)}")
    for p in profiles:
        click.echo(f"  - {p}")


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == '__main__':
    main()
