"""add default_kill_chain_model to app_settings

Revision ID: b8e1f4a29d6c
Revises: a3f6d1c9e7b4
Create Date: 2026-09-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e1f4a29d6c'
down_revision = 'a3f6d1c9e7b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'app_settings',
        sa.Column('default_kill_chain_model', sa.String(length=20), nullable=False, server_default='lmckc'),
    )


def downgrade():
    op.drop_column('app_settings', 'default_kill_chain_model')
