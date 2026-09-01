"""add kill_chain_model to engagements

Revision ID: f1a6b8d3c7e2
Revises: e7c3f9a2d5b1
Create Date: 2026-08-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a6b8d3c7e2'
down_revision = 'e7c3f9a2d5b1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'engagements',
        sa.Column('kill_chain_model', sa.String(length=20), nullable=False, server_default='lmckc'),
    )


def downgrade():
    op.drop_column('engagements', 'kill_chain_model')
