"""add data to samsara vehicles

Revision ID: add_samsara_data
Revises: add_samsara_external_ids
Create Date: 2024-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'add_samsara_data'
down_revision = 'add_samsara_external_ids'
branch_labels = None
depends_on = None


def upgrade():
    # Add data column as JSONB
    op.add_column('samsara_vehicles', 
                  sa.Column('data', 
                           postgresql.JSONB(astext_type=sa.Text()), 
                           nullable=True,
                           server_default='{}'))


def downgrade():
    op.drop_column('samsara_vehicles', 'data') 