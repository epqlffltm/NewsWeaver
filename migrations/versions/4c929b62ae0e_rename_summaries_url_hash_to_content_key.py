"""rename summaries url_hash to content_key

Revision ID: 4c929b62ae0e
Revises: 456b227a5b03
Create Date: 2026-09-02 17:35:33.904882

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4c929b62ae0e'
down_revision: str | Sequence[str] | None = '456b227a5b03'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 요약 대상 식별 방식이 기사 단위에서 그룹 단위로 바뀌어 기존 키를 옮길 수
    # 없다. 프롬프트 버전도 함께 올라 어차피 재생성되므로 비우고 시작한다
    op.execute("DELETE FROM summaries")

    op.add_column(
        'summaries',
        sa.Column('content_key', sa.String(length=64), nullable=False),
    )
    op.drop_index(op.f('ix_summaries_url_hash'), table_name='summaries')
    op.drop_constraint(
        op.f('uq_summaries_article_and_config'), 'summaries', type_='unique'
    )
    op.create_index(
        'ix_summaries_content_key', 'summaries', ['content_key'], unique=False
    )
    op.create_unique_constraint(
        'uq_summaries_content_and_config',
        'summaries',
        ['content_key', 'model_name', 'prompt_version'],
    )
    op.drop_column('summaries', 'url_hash')


def downgrade() -> None:
    """Downgrade schema."""
    # 되돌릴 때도 그룹 키를 기사 키로 환원할 수 없으므로 비운다
    op.execute("DELETE FROM summaries")

    op.add_column(
        'summaries',
        sa.Column(
            'url_hash', sa.VARCHAR(length=64), autoincrement=False, nullable=False
        ),
    )
    op.drop_constraint('uq_summaries_content_and_config', 'summaries', type_='unique')
    op.drop_index('ix_summaries_content_key', table_name='summaries')
    op.create_unique_constraint(
        op.f('uq_summaries_article_and_config'),
        'summaries',
        ['url_hash', 'model_name', 'prompt_version'],
        postgresql_nulls_not_distinct=False,
    )
    op.create_index(op.f('ix_summaries_url_hash'), 'summaries', ['url_hash'], unique=False)
    op.drop_column('summaries', 'content_key')