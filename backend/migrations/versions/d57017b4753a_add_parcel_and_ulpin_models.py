"""add_parcel_and_ulpin_models

Revision ID: d57017b4753a
Revises: 
Create Date: 2026-09-16 16:20:36.965206

"""
from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd57017b4753a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    parcel_status = sa.Enum(
        'draft', 'registered', 'active', 'archived',
        name='parcel_status',
        create_type=True,
    )
    parcel_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'parcels',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('parcel_identifier', sa.String(length=255), nullable=False),
        sa.Column('ulpin', sa.String(length=255), nullable=False),
        sa.Column('geometry', geoalchemy2.Geometry(geometry_type='MULTIPOLYGON', srid=4326), nullable=False),
        sa.Column('area_sqm', sa.Float(), nullable=False),
        sa.Column('status', parcel_status, nullable=False),
        sa.Column('metadata', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parcel_identifier', name='uq_parcels_parcel_identifier'),
        sa.UniqueConstraint('ulpin', name='uq_parcels_ulpin'),
    )
    op.create_index('ix_parcels_ulpin', 'parcels', ['ulpin'], unique=False)
    op.create_index('idx_parcels_geometry', 'parcels', ['geometry'], unique=False, postgresql_using='gist')

    op.create_table(
        'ulpins',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('parcel_id', sa.Uuid(), nullable=False),
        sa.Column('ulpin_code', sa.String(length=255), nullable=False),
        sa.Column('issued_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('issuing_authority', sa.String(length=255), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parcel_id', name='uq_ulpins_parcel_id'),
        sa.UniqueConstraint('ulpin_code', name='uq_ulpins_ulpin_code'),
    )
    op.create_index('ix_ulpins_ulpin_code', 'ulpins', ['ulpin_code'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ulpins_ulpin_code', table_name='ulpins')
    op.drop_table('ulpins')
    op.drop_index('idx_parcels_geometry', table_name='parcels', postgresql_using='gist')
    op.drop_index('ix_parcels_ulpin', table_name='parcels')
    op.drop_table('parcels')

    parcel_status = sa.Enum('draft', 'registered', 'active', 'archived', name='parcel_status')
    parcel_status.drop(op.get_bind(), checkfirst=True)
