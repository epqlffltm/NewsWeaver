# NewsWeaver/scripts/spike_check_dedupe.py

"""
준중복 제거가 실제 선별 결과에서 무엇을 걸러내는지 확인한다.

임계값은 모델의 유사도 분포에 따라 달라지므로 추측으로 정할 수 없다.
여러 값을 나란히 적용해 무엇이 묶이고 무엇이 남는지 눈으로 비교해야
적절한 값을 고를 수 있다.
"""

from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.config import get_settings
from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.db.tables import ArticleRow
from news_weaver.domain.article import Article
from news_weaver.selection.dedupe import remove_near_duplicates
from news_weaver.selection.interests import INTEREST_TOPICS, MAX_ARTICLES_PER_RUN
from news_weaver.selection.keyword import select_articles

load_dotenv()

# 임계값 후보. 낮을수록 많이 묶이고, 지나치면 별개 사건까지 사라진다
THRESHOLD_CANDIDATES = (0.50, 0.55, 0.60, 0.65)


def load_all_articles(session) -> list[Article]:
    """저장된 기사를 모두 도메인 모델로 읽어온다."""
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
    session_factory = get_session_factory()

    with session_factory() as session:
        articles = load_all_articles(session)
        selected = select_articles(articles, INTEREST_TOPICS, MAX_ARTICLES_PER_RUN * 2)

        if not selected:
            print("선별된 기사가 없습니다.")
            return

        print(f"선별 {len(selected)}건\n")
        for item in selected:
            print(f"  [{item.score}점] {item.article.title[:50]}")

        repository = ArticleRepository(session)
        url_hashes = [item.article.url_hash for item in selected]

        for threshold in THRESHOLD_CANDIDATES:
            pairs = repository.find_similarity_pairs(
                url_hashes,
                settings.embedding_model,
                threshold,
            )
            report = remove_near_duplicates(selected, pairs)

            print(f"\n{'=' * 70}")
            print(f"임계값 {threshold} → 남김 {len(report.kept)}건 ")
            print(f"/ 제외 {len(report.removed)}건")

            for removed_title, representative in report.removed:
                print(f"  제외: {removed_title[:40]}")
                print(f"    ← {representative[:40]}")


if __name__ == "__main__":
    main()