"""add embedding columns to articles

Revision ID: 456b227a5b03
Revises: e87bc02e79d8
Create Date: 2026-09-02 13:31:31.709604

"""
from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '456b227a5b03'
down_revision: str | Sequence[str] | None = 'e87bc02e79d8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector 확장이 있어야 vector 타입을 쓸 수 있다.
    # autogenerate는 확장 설치를 감지하지 못하므로 직접 추가한다
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        'articles',
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    )
    op.add_column(
        'articles',
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
    )
    op.add_column(
        'articles',
        sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 확장은 다른 테이블이 쓰고 있을 수 있으므로 제거하지 않는다
    op.drop_column('articles', 'embedded_at')
    op.drop_column('articles', 'embedding_model')
    op.drop_column('articles', 'embedding')