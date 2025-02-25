"""create point transactions table

Revision ID: create_point_transactions
Create Date: 2024-02-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'create_point_transactions'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create point_transaction table
    op.create_table(
        'point_transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(255)),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(50)),
        sa.Column('reference_id', sa.Integer()),
        sa.Column('transaction_metadata', JSONB),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better query performance
    op.create_index('ix_point_transaction_user_id', 'point_transaction', ['user_id'])
    op.create_index('ix_point_transaction_timestamp', 'point_transaction', ['timestamp'])
    op.create_index('ix_point_transaction_activity_type', 'point_transaction', ['activity_type'])

def downgrade():
    op.drop_table('point_transaction') 