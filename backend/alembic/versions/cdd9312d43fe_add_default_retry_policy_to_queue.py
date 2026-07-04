"""Add default retry policy to queue

Revision ID: cdd9312d43fe
Revises: ce34d5d50ce6
Create Date: 2026-07-04 17:59:56.139799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cdd9312d43fe'
down_revision: Union[str, None] = 'ce34d5d50ce6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('queues', sa.Column('default_retry_strategy', sa.String(length=50), server_default='fixed', nullable=False))
    op.add_column('queues', sa.Column('default_max_retries', sa.Integer(), server_default='3', nullable=False))
    op.add_column('queues', sa.Column('default_retry_delay', sa.Integer(), server_default='5', nullable=False))
    op.add_column('queues', sa.Column('default_backoff_factor', sa.Float(), server_default='2.0', nullable=False))


def downgrade() -> None:
    op.drop_column('queues', 'default_backoff_factor')
    op.drop_column('queues', 'default_retry_delay')
    op.drop_column('queues', 'default_max_retries')
    op.drop_column('queues', 'default_retry_strategy')

