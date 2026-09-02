# NewsWeaver/scripts/spike_run_summary.py

"""
선별된 기사에 실제 요약기를 적용해 결과를 눈으로 확인하는 스파이크 스크립트.

프롬프트가 수치와 고유명사를 지켜내는지, 원문에 없는 내용을 만들어내지 않는지는
실제 기사로 돌려봐야 알 수 있다. 건당 수십 초에서 수 분이 걸리므로 소수만 처리한다.
"""

import time

from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.db.engine import get_session_factory
from news_weaver.db.tables import ArticleRow
from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS
from news_weaver.selection.keyword import select_articles
from news_weaver.summarize.ollama import OllamaSummarizer

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


def print_comparison(article: Article, summary_text: str, elapsed_seconds: float) -> None:
    """원문과 요약을 나란히 출력해 정보 손실을 눈으로 비교할 수 있게 한다."""
    print(f"\n{'=' * 70}")
    print(f"제목: {article.title}")
    print(f"소요: {elapsed_seconds:.1f}초")
    print(f"\n[원문]\n{(article.summary or '(본문 없음)')[:400]}")
    print(f"\n[요약]\n{summary_text}")


def main() -> None:
    articles = load_all_articles()
    selected = select_articles(articles, INTEREST_TOPICS, SAMPLE_SIZE)

    if not selected:
        print("선별된 기사가 없습니다. 먼저 수집을 실행하세요.")
        return

    summarizer = OllamaSummarizer()
    print(f"{len(selected)}건을 요약합니다. 시간이 걸립니다.\n")

    for item in selected:
        started_at = time.perf_counter()
        result = summarizer.summarize([item.article])[0]
        elapsed_seconds = time.perf_counter() - started_at

        if result.is_success:
            print_comparison(item.article, result.summary_text, elapsed_seconds)
        else:
            print(f"\n실패: {item.article.title[:40]} — {result.error}")


if __name__ == "__main__":
    main()