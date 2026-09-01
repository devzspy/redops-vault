"""add backup_run_logs

Revision ID: a3f6d1c9e7b4
Revises: f1a6b8d3c7e2
Create Date: 2026-08-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f6d1c9e7b4'
down_revision = 'f1a6b8d3c7e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'backup_run_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('destination_id', sa.Integer(), nullable=False),
        sa.Column('ran_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(length=20), nullable=False),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['destination_id'], ['backup_destinations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_backup_run_logs_destination_id'), 'backup_run_logs', ['destination_id'], unique=False
    )


def downgrade():
    op.drop_index(op.f('ix_backup_run_logs_destination_id'), table_name='backup_run_logs')
    op.drop_table('backup_run_logs')
