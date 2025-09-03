"""Initial schema

Revision ID: cfd6bf1e36a6
Revises:
Create Date: 2025-09-03 03:49:34.936399

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cfd6bf1e36a6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    run_status = sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled', name='runstatus')
    artifact_kind = sa.Enum(
        'input_file', 'output_csv', 'output_json', 'output_xml', 'output_pdf',
        'metadata', 'error_log', 'validation_report', 'mapping_profile',
        name='artifactkind'
    )

    run_status.create(op.get_bind(), checkfirst=True)
    artifact_kind.create(op.get_bind(), checkfirst=True)

    # datasets
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('org_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('profile', sa.String(), nullable=False),
        sa.Column('schedule_cron', sa.String()),
        sa.Column('publish_target', sa.String()),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.UniqueConstraint('org_id', 'name', name='uq_dataset_org_name'),
    )
    op.create_index('idx_dataset_org_profile', 'datasets', ['org_id', 'profile'])
    op.create_index(op.f('ix_datasets_org_id'), 'datasets', ['org_id'])

    # mappings
    op.create_table(
        'mappings',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('dataset_id', sa.String(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('json_spec', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)')),
    )
    op.create_index('idx_mapping_dataset_version', 'mappings', ['dataset_id', 'version'])

    # runs
    op.create_table(
        'runs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('dataset_id', sa.String(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('finished_at', sa.DateTime()),
        sa.Column('status', run_status, nullable=False, server_default='pending'),
        sa.Column('input_hash', sa.String()),
        sa.Column('output_hash', sa.String()),
        sa.Column('message', sa.Text()),
        sa.Column('rows_processed', sa.Integer()),
        sa.Column('rows_valid', sa.Integer()),
        sa.Column('rows_invalid', sa.Integer()),
        sa.Column('external_package_id', sa.String()),
        sa.Column('external_resource_id', sa.String()),
    )
    op.create_index('idx_run_dataset_started', 'runs', ['dataset_id', 'started_at'])
    op.create_index('idx_run_status_started', 'runs', ['status', 'started_at'])

    # artifacts
    op.create_table(
        'artifacts',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('run_id', sa.String(), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', artifact_kind, nullable=False),
        sa.Column('path', sa.String(), nullable=False),
        sa.Column('checksum', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.Integer()),
        sa.Column('mime_type', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)')),
    )
    op.create_index('idx_artifact_run_kind', 'artifacts', ['run_id', 'kind'])
    op.create_index('idx_artifact_checksum', 'artifacts', ['checksum'])


def downgrade() -> None:
    op.drop_index('idx_artifact_checksum', table_name='artifacts')
    op.drop_index('idx_artifact_run_kind', table_name='artifacts')
    op.drop_table('artifacts')

    op.drop_index('idx_run_status_started', table_name='runs')
    op.drop_index('idx_run_dataset_started', table_name='runs')
    op.drop_table('runs')

    op.drop_index('idx_mapping_dataset_version', table_name='mappings')
    op.drop_table('mappings')

    op.drop_index('ix_datasets_org_id', table_name='datasets')
    op.drop_index('idx_dataset_org_profile', table_name='datasets')
    op.drop_table('datasets')

    # Enums
    run_status = sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled', name='runstatus')
    artifact_kind = sa.Enum(
        'input_file', 'output_csv', 'output_json', 'output_xml', 'output_pdf',
        'metadata', 'error_log', 'validation_report', 'mapping_profile',
        name='artifactkind'
    )
    artifact_kind.drop(op.get_bind(), checkfirst=True)
    run_status.drop(op.get_bind(), checkfirst=True)
