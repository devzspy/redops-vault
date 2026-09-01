"""add engagement_links

Revision ID: 9d4c2f6e1a83
Revises: 7b1e4d6a9f02
Create Date: 2026-08-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d4c2f6e1a83'
down_revision = '7b1e4d6a9f02'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'engagement_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engagement_id', sa.Integer(), nullable=False),
        sa.Column('link_type', sa.String(length=20), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_by_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['added_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_engagement_links_engagement_id'),
        'engagement_links',
        ['engagement_id'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_engagement_links_engagement_id'), table_name='engagement_links')
    op.drop_table('engagement_links')
