"""add commission settings table

Revision ID: add_commission_settings
Revises: add_commission_models
Create Date: 2024-02-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_commission_settings'
down_revision = 'add_commission_models'
branch_labels = None
depends_on = None


def upgrade():
    # Create commission_settings table
    op.create_table('commission_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    
    # Insert default settings
    op.execute("""
        INSERT INTO commission_settings (key, value, description, created_at, updated_at)
        VALUES 
        ('first_2_years_rate', 0.10, 'Commission rate for the first 2 years (24 months)', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('after_2_years_rate', 0.025, 'Commission rate after 2 years (month 25+)', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('network_commission_rate', 0.025, 'Commission rate for partners on their network''s sales', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)


def downgrade():
    op.drop_table('commission_settings') 