# NewsWeaver/scripts/spike_check_selection.py

"""
저장된 기사에 주제 선별을 적용해 결과를 눈으로 확인하는 스파이크 스크립트.

문자열 매칭은 등록되지 않은 표현을 놓치고 부분 일치로 엉뚱한 기사를 잡는다.
그 한계가 실제 데이터에서 어떻게 나타나는지 확인해야 다음 단계(벡터 검색)가
무엇을 개선해야 하는지 판단할 수 있다.
"""

from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.db.engine import get_session_factory
from news_weaver.db.tables import ArticleRow
from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS, MAX_ARTICLES_PER_RUN
from news_weaver.selection.keyword import select_articles

load_dotenv()


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
    articles = load_all_articles()
    topic_names = ", ".join(topic.name for topic in INTEREST_TOPICS)

    print(f"저장된 기사 {len(articles)}건")
    print(f"주제: {topic_names}\n")

    # 상한이 실제로 몇 건을 잘라내는지 보기 위해 전체 매칭 수를 먼저 구한다
    all_matched = select_articles(articles, INTEREST_TOPICS, limit=len(articles))
    selected = all_matched[:MAX_ARTICLES_PER_RUN]

    print(f"주제 매칭 {len(all_matched)}건 / 상한 적용 후 {len(selected)}건\n")

    for rank, item in enumerate(selected, start=1):
        matched = ", ".join(item.matched_topics)
        print(f"{rank:2}. [{item.score}점] {item.article.title[:45]}")
        print(f"     걸린 주제: {matched}")


if __name__ == "__main__":
    main()