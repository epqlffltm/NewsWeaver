# NewsWeaver/src/news_weaver/selection/keyword.py

"""
등록된 키워드를 기준으로 요약 대상 기사를 선별한다.

요약은 건당 수십 초가 걸리므로 수집한 기사를 전부 처리할 수 없다.
관심사와 가까운 것부터 정해진 건수만 넘기는 것이 이 모듈의 책임이다.

문자열 포함 여부만 보므로 표현이 다르면 놓친다. 이 한계를 실제로 겪은 뒤에
벡터 검색으로 넓히는 것이 다음 단계다.
"""

from dataclasses import dataclass

from news_weaver.domain.article import Article

# 제목에 나온 키워드는 기사의 주제일 가능성이 높아 더 높게 평가한다
TITLE_MATCH_SCORE = 3
SUMMARY_MATCH_SCORE = 1


@dataclass(frozen=True, slots=True)
class ScoredArticle:
    """선별 점수가 매겨진 기사."""

    article: Article
    score: int

    # 어떤 키워드에 걸렸는지. 선별 결과를 검토할 때 근거가 된다
    matched_keywords: tuple[str, ...]


def _count_keyword_score(article: Article, keyword: str) -> int:
    """키워드 하나가 기사에서 얻는 점수를 계산한다."""
    normalized_keyword = keyword.lower()

    score = 0
    if normalized_keyword in article.title.lower():
        score += TITLE_MATCH_SCORE
    if article.summary and normalized_keyword in article.summary.lower():
        score += SUMMARY_MATCH_SCORE

    return score


def score_article(article: Article, keywords: tuple[str, ...]) -> ScoredArticle:
    """기사가 키워드 목록에 대해 얻는 총점과 걸린 키워드를 계산한다."""
    total_score = 0
    matched: list[str] = []

    for keyword in keywords:
        keyword_score = _count_keyword_score(article, keyword)
        if keyword_score > 0:
            total_score += keyword_score
            matched.append(keyword)

    return ScoredArticle(
        article=article,
        score=total_score,
        matched_keywords=tuple(matched),
    )


def select_articles(
    articles: list[Article],
    keywords: tuple[str, ...],
    limit: int,
) -> list[ScoredArticle]:
    """
    키워드에 걸린 기사를 점수 높은 순으로 정해진 건수만 반환한다.

    요약 비용이 건당 수십 초이므로 상한은 선택이 아니라 필수다.
    """
    scored = [score_article(article, keywords) for article in articles]
    matched = [item for item in scored if item.score > 0]

    matched.sort(key=lambda item: item.score, reverse=True)

    return matched[:limit]