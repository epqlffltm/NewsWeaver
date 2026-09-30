# NewsWeaver/migrations/versions/878eb77d86a7_create_deliveries_table.py

"""create deliveries table

Revision ID: 878eb77d86a7
Revises: b2e96feab1f5
Create Date: 2026-09-30 07:52:17.193710

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '878eb77d86a7'
down_revision: str | Sequence[str] | None = 'b2e96feab1f5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 선별 후보가 최근 며칠치라, 발송 이력이 없으면 같은 기사가 반복 발송된다
    op.create_table('deliveries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('delivery_date', sa.Date(), nullable=False),
    sa.Column('recipient', sa.String(length=320), nullable=False),
    sa.Column('subject', sa.Text(), nullable=False),
    sa.Column('content_keys', postgresql.ARRAY(sa.String(length=64)), nullable=False),
    sa.Column('url_hashes', postgresql.ARRAY(sa.String(length=64)), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deliveries_date_recipient', 'deliveries', ['delivery_date', 'recipient'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_deliveries_date_recipient', table_name='deliveries')
    op.drop_table('deliveries')
