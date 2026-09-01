"""add threat_models

Revision ID: 7b1e4d6a9f02
Revises: a5e9c7f21b3d
Create Date: 2026-08-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b1e4d6a9f02'
down_revision = 'a5e9c7f21b3d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'threat_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engagement_id', sa.Integer(), nullable=False),
        sa.Column('threat_model', sa.Text(), nullable=True),
        sa.Column('attack_plan', sa.Text(), nullable=True),
        sa.Column('objectives', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engagement_id'),
    )


def downgrade():
    op.drop_table('threat_models')
