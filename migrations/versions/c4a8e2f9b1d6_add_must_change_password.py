"""add must_change_password to users

Revision ID: c4a8e2f9b1d6
Revises: b2f7a1c9e3d4
Create Date: 2026-08-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4a8e2f9b1d6'
down_revision = 'b2f7a1c9e3d4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column('users', 'must_change_password')
