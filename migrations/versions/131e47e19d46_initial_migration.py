"""initial migration

Revision ID: 131e47e19d46
Revises: 
Create Date: 2025-02-04 15:21:24.892608

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '131e47e19d46'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('reset_token', sa.String(length=100), nullable=True),
    sa.Column('reset_token_expiry', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('reset_token')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user')
    # ### end Alembic commands ###
