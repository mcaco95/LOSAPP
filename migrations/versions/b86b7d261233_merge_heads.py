"""merge heads

Revision ID: b86b7d261233
Revises: nullable_vid, b241242f0648
Create Date: 2025-05-22 16:55:53.428532

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b86b7d261233'
down_revision = ('nullable_vid', 'b241242f0648')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
