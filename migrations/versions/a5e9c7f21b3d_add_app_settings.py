"""add app_settings

Revision ID: a5e9c7f21b3d
Revises: d39a50a64c1b
Create Date: 2026-08-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5e9c7f21b3d'
down_revision = 'd39a50a64c1b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('infra_mode', sa.String(length=20), nullable=False),
        sa.Column('engagement_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('app_settings')
