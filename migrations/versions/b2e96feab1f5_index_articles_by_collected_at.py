# NewsWeaver/migrations/versions/b2e96feab1f5_index_articles_by_collected_at.py

"""index articles by collected_at

Revision ID: b2e96feab1f5
Revises: 4c929b62ae0e
Create Date: 2026-09-30 07:50:40.303897

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2e96feab1f5'
down_revision: str | Sequence[str] | None = '4c929b62ae0e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 실제 조회는 모두 collected_at으로 거르고 정렬한다. published_at 인덱스는
    # 어떤 쿼리도 쓰지 않아 쓰기 비용만 늘리므로 교체한다
    op.drop_index('ix_articles_published_at', table_name='articles')
    op.create_index(
        'ix_articles_collected_at',
        'articles',
        [sa.literal_column('collected_at DESC')],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_articles_collected_at', table_name='articles')
    op.create_index(
        'ix_articles_published_at',
        'articles',
        [sa.literal_column('published_at DESC')],
        unique=False,
    )
