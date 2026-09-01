"""add engagement_assignments and api_keys tables

Revision ID: b2f7a1c9e3d4
Revises: 9d4c2f6e1a83
Create Date: 2026-08-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2f7a1c9e3d4'
down_revision = '9d4c2f6e1a83'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'engagement_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engagement_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['assigned_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engagement_id', 'user_id', name='uq_engagement_assignment'),
    )
    op.create_index(
        op.f('ix_engagement_assignments_engagement_id'),
        'engagement_assignments',
        ['engagement_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_engagement_assignments_user_id'),
        'engagement_assignments',
        ['user_id'],
        unique=False,
    )

    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('key_prefix', sa.String(length=12), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
    )
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys')
    op.drop_table('api_keys')

    op.drop_index(op.f('ix_engagement_assignments_user_id'), table_name='engagement_assignments')
    op.drop_index(op.f('ix_engagement_assignments_engagement_id'), table_name='engagement_assignments')
    op.drop_table('engagement_assignments')
