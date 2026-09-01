"""add engagement_deletion_requests

Revision ID: e7c3f9a2d5b1
Revises: c4a8e2f9b1d6
Create Date: 2026-08-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7c3f9a2d5b1'
down_revision = 'c4a8e2f9b1d6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'engagement_deletion_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engagement_id', sa.Integer(), nullable=False),
        sa.Column('requested_by_id', sa.Integer(), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_engagement_deletion_requests_engagement_id'),
        'engagement_deletion_requests',
        ['engagement_id'],
        unique=True,
    )


def downgrade():
    op.drop_index(
        op.f('ix_engagement_deletion_requests_engagement_id'), table_name='engagement_deletion_requests'
    )
    op.drop_table('engagement_deletion_requests')
