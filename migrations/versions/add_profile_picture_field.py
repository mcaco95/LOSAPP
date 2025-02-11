"""add profile picture field

Revision ID: add_profile_picture_field
Revises: b40c6db21d43
Create Date: 2025-02-11 10:59:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_profile_picture_field'
down_revision = 'add_points_and_rewards'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('user', sa.Column('profile_picture', sa.String(length=255), nullable=True))

def downgrade():
    op.drop_column('user', 'profile_picture')
