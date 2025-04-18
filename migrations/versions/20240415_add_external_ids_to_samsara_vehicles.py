"""add external_ids to samsara vehicles

Revision ID: add_samsara_external_ids
Revises: alter_samsara_alerts_vehicle_id
Create Date: 2024-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'add_samsara_external_ids'
down_revision = 'alter_samsara_alerts_vehicle_id'
branch_labels = None
depends_on = None


def upgrade():
    # Add external_ids column as JSONB
    op.add_column('samsara_vehicles', 
                  sa.Column('external_ids', 
                           postgresql.JSONB(astext_type=sa.Text()), 
                           nullable=True,
                           server_default='{}'))


def downgrade():
    op.drop_column('samsara_vehicles', 'external_ids') 