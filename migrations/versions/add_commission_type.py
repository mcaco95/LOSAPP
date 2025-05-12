"""add commission type field

Revision ID: 2f6e4a9b8d3c
Revises: 81e6da7527cd
Create Date: 2024-03-10 21:16:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '2f6e4a9b8d3c'
down_revision = '81e6da7527cd'
branch_labels = None
depends_on = None

def upgrade():
    # Add commission_type column with default value 'safety'
    op.add_column('commission', sa.Column('commission_type', sa.String(20), nullable=True))
    
    # Update existing rows to have 'safety' as the commission_type
    op.execute("UPDATE commission SET commission_type = 'safety' WHERE commission_type IS NULL")
    
    # Make the column non-nullable after setting default values
    op.alter_column('commission', 'commission_type',
                    existing_type=sa.String(20),
                    nullable=False,
                    server_default=sa.text("'safety'::character varying"))

def downgrade():
    # Remove commission_type column
    op.drop_column('commission', 'commission_type') 