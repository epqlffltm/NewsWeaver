# NewsWeaver/scripts/spike_run_summary.py

"""
선별된 기사를 캐시와 함께 요약해 결과와 소요 시간을 확인하는 스파이크 스크립트.

두 번 실행했을 때 두 번째가 즉시 끝나야 캐시가 제 역할을 하는 것이다.
요약 품질은 원문과 나란히 출력해 정보 손실을 눈으로 비교한다.
"""

import time

from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.config import get_settings
from news_weaver.db.engine import get_session_factory
from news_weaver.db.summary_repository import SummaryRepository
from news_weaver.db.tables import ArticleRow
from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS
from news_weaver.selection.keyword import select_articles
from news_weaver.summarize.ollama import OllamaSummarizer
from news_weaver.summarize.prompt import PROMPT_VERSION
from news_weaver.summarize.service import summarize_with_cache

load_dotenv()

# 확인이 목적이므로 배치 상한과 별개로 더 적게 처리한다
SAMPLE_SIZE = 3


def load_all_articles() -> list[Article]:
    """저장된 기사를 모두 도메인 모델로 읽어온다."""
    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(select(ArticleRow)).scalars().all()

    return [
        Article(
            source_name=row.source_name,
            title=row.title,
            url=row.url,
            url_hash=row.url_hash,
            collected_at=row.collected_at,
            published_at=row.published_at,
            author=row.author,
            summary=row.summary,
        )
        for row in rows
    ]


def main() -> None:
    settings = get_settings()
    articles = load_all_articles()
    selected = select_articles(articles, INTEREST_TOPICS, SAMPLE_SIZE)

    if not selected:
        print("선별된 기사가 없습니다. 먼저 수집을 실행하세요.")
        return

    print(f"{len(selected)}건을 요약합니다. 모델: {settings.ollama_model}\n")

    session_factory = get_session_factory()
    started_at = time.perf_counter()

    with session_factory() as session:
        report = summarize_with_cache(
            [item.article for item in selected],
            OllamaSummarizer(),
            SummaryRepository(session),
            settings.ollama_model,
            PROMPT_VERSION,
        )
        session.commit()

    elapsed_seconds = time.perf_counter() - started_at

    print(f"소요 {elapsed_seconds:.1f}초 / ")
    print(f"캐시 {report.cache_hit_count}건 / 생성 {report.generated_count}건")

    for failed_title, reason in report.failures:
        print(f"실패: {failed_title[:40]} — {reason}")

    for item in report.summarized:
        print(f"\n{'=' * 70}")
        print(f"제목: {item.article.title}")
        print(f"\n[원문]\n{(item.article.summary or '(본문 없음)')[:300]}")
        print(f"\n[요약]\n{item.summary_text}")


if __name__ == "__main__":
    main()