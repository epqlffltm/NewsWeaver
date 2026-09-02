# NewsWeaver/src/news_weaver/selection/keyword.py

"""
등록된 주제를 기준으로 요약 대상 기사를 선별한다.

요약은 건당 수십 초가 걸리므로 수집한 기사를 전부 처리할 수 없다.
관심사와 가까운 것부터 정해진 건수만 넘기는 것이 이 모듈의 책임이다.

문자열 포함 여부만 보므로 등록되지 않은 표현은 놓친다. 이 한계를 실제로
겪은 뒤에 벡터 검색으로 넓히는 것이 다음 단계다.
"""

from dataclasses import dataclass

from news_weaver.domain.article import Article
from news_weaver.selection.interests import Topic

# 제목에 나온 표현은 기사의 주제일 가능성이 높아 더 높게 평가한다
TITLE_MATCH_SCORE = 3
SUMMARY_MATCH_SCORE = 1


@dataclass(frozen=True, slots=True)
class ScoredArticle:
    """선별 점수가 매겨진 기사."""

    article: Article
    score: int

    # 어떤 주제에 걸렸는지. 선별 결과를 검토할 때 근거가 된다
    matched_topics: tuple[str, ...]


def _score_topic(article: Article, topic: Topic) -> int:
    """
    주제 하나가 기사에서 얻는 점수를 계산한다.

    같은 주제의 표현이 여러 개 걸려도 한 번만 점수를 준다.
    "인공지능(AI)"처럼 병기하는 관습 때문에 점수가 부풀지 않도록 하기 위함이다.
    """
    lowered_title = article.title.lower()
    lowered_summary = article.summary.lower() if article.summary else ""

    found_in_title = any(
        expression.lower() in lowered_title for expression in topic.expressions
    )
    found_in_summary = any(
        expression.lower() in lowered_summary for expression in topic.expressions
    )

    score = 0
    if found_in_title:
        score += TITLE_MATCH_SCORE
    if found_in_summary:
        score += SUMMARY_MATCH_SCORE

    return score


def score_article(article: Article, topics: tuple[Topic, ...]) -> ScoredArticle:
    """기사가 주제 목록에 대해 얻는 총점과 걸린 주제를 계산한다."""
    total_score = 0
    matched: list[str] = []

    for topic in topics:
        topic_score = _score_topic(article, topic)
        if topic_score > 0:
            total_score += topic_score
            matched.append(topic.name)

    return ScoredArticle(
        article=article,
        score=total_score,
        matched_topics=tuple(matched),
    )


def select_articles(
    articles: list[Article],
    topics: tuple[Topic, ...],
    limit: int,
) -> list[ScoredArticle]:
    """
    주제에 걸린 기사를 점수 높은 순으로 정해진 건수만 반환한다.

    요약 비용이 건당 수십 초이므로 상한은 선택이 아니라 필수다.
    """
    scored = [score_article(article, topics) for article in articles]
    matched = [item for item in scored if item.score > 0]

    matched.sort(key=lambda item: item.score, reverse=True)

    return matched[:limit]