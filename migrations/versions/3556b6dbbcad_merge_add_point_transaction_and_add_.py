"""merge add_point_transaction and add_service_status_fields

Revision ID: 3556b6dbbcad
Revises: add_point_transaction, add_service_status_fields
Create Date: 2025-03-09 10:27:28.210404

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '3556b6dbbcad'
down_revision = ('add_point_transaction', 'add_service_status_fields')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no need to create tables
    # Both parent migrations will handle their own changes
    pass


def downgrade():
    # This is a merge migration - no need to drop tables
    # Both parent migrations will handle their own changes
    pass
