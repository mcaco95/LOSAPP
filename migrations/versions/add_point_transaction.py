"""add point transaction table

Revision ID: add_point_transaction
Revises: add_commission_settings
Create Date: 2025-02-28 12:46:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_point_transaction'
down_revision = 'add_commission_settings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('point_transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('transaction_metadata', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_point_transaction_timestamp'), 'point_transaction', ['timestamp'], unique=False)
    op.create_index(op.f('ix_point_transaction_user_id'), 'point_transaction', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_point_transaction_user_id'), table_name='point_transaction')
    op.drop_index(op.f('ix_point_transaction_timestamp'), table_name='point_transaction')
    op.drop_table('point_transaction') 