# NewsWeaver/scripts/spike_check_similarity.py

"""
벡터 유사도 검색이 키워드로 잡지 못하는 기사를 찾아내는지 확인한다.

키워드 선별의 한계는 등록된 표현이 없으면 아예 걸리지 않는다는 점이다.
그 빈틈을 벡터 검색이 실제로 메우는지 보려면, 키워드 상위 기사를 기준으로
유사 기사를 뽑아 키워드에 걸렸는지 여부를 함께 표시해야 한다.
"""

from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.config import get_settings
from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.db.tables import ArticleRow
from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS
from news_weaver.selection.keyword import score_article, select_articles

load_dotenv()

# 기준으로 삼을 키워드 상위 기사 수
SEED_COUNT = 3

# 기준 하나당 끌어올 유사 기사 수
NEIGHBOR_COUNT = 5


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
        seeds = select_articles(articles, INTEREST_TOPICS, SEED_COUNT)

        if not seeds:
            print("키워드에 걸린 기사가 없습니다.")
            return

        repository = ArticleRepository(session)
        seed_hashes = [item.article.url_hash for item in seeds]

        for seed in seeds:
            print(f"\n{'=' * 70}")
            print(f"[기준] {seed.article.title[:50]}")
            print(f"       {seed.score}점 / {', '.join(seed.matched_topics)}")

            neighbors = repository.find_similar_articles(
                seed.article.url_hash,
                settings.embedding_model,
                NEIGHBOR_COUNT,
                seed_hashes,
            )

            for article, similarity in neighbors:
                # 키워드로도 잡히는 기사인지 표시해, 벡터가 실제로 넓히는
                # 범위를 눈으로 구분할 수 있게 한다
                keyword_score = score_article(article, INTEREST_TOPICS).score
                marker = "키워드O" if keyword_score > 0 else "키워드X"

                print(f"  {similarity:.3f} [{marker}] {article.title[:45]}")


if __name__ == "__main__":
    main()