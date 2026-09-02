# NewsWeaver/src/news_weaver/summarize/prompt.py

"""
요약 프롬프트와 그 버전을 관리한다.

프롬프트는 요약 품질을 좌우하며 자주 수정된다. 수정 시 기존 캐시가 남아
있으면 옛 결과가 그대로 나오므로, 버전을 함께 두어 무효화 근거로 삼는다.

문장 수를 강제하면 원문에 내용이 부족할 때 모델이 없는 내용을 만들어내므로
상한만 둔다. 수치와 고유명사는 요약에서 가장 쉽게 소실되는 정보라 명시적으로
유지를 요구한다.

여러 매체가 같은 사건을 다룬 경우 각 기사가 강조하는 부분이 다르므로,
함께 넣어 종합하면 단일 기사보다 정보가 풍부해진다. 다만 서로 어긋나는
내용이 섞일 수 있어 추측으로 메우지 않도록 명시한다.
"""

from news_weaver.domain.article import Article

# 프롬프트를 수정할 때마다 올린다. 요약 캐시의 키 일부로 쓰인다
PROMPT_VERSION = "v3"

_SINGLE_TEMPLATE = """다음 뉴스를 한국어로 3문장 이내로 요약해줘.

규칙:
- 원문에 없는 내용, 평가, 전망을 추가하지 마
- 구체적인 수치와 고유명사는 그대로 유지해
- 신문 기사체(~했다, ~이다)로 작성해
- 요약문만 출력하고 다른 말은 붙이지 마

제목: {title}
본문: {body}"""

_BRIEFING_TEMPLATE = """같은 사건을 다룬 여러 기사다. 하나의 브리핑으로 종합해줘.

규칙:
- 한국어로 4문장 이내
- 기사에 없는 내용, 평가, 전망을 추가하지 마
- 기사마다 다루는 내용이 다르면 모두 포함해
- 구체적인 수치와 고유명사는 그대로 유지해
- 내용이 서로 어긋나면 어느 한쪽만 택하지 말고 둘 다 언급해
- 신문 기사체(~했다, ~이다)로 작성해
- 브리핑 본문만 출력하고 다른 말은 붙이지 마

{articles}"""

_ARTICLE_BLOCK = """[기사 {index}] {source}
제목: {title}
본문: {body}"""


def _article_body(article: Article) -> str:
    """요약에 넣을 본문을 고른다. 없는 소스는 제목만으로 처리한다."""
    return article.summary or "(본문 없음. 제목만으로 요약)"


def build_summary_prompt(article: Article) -> str:
    """기사 하나를 요약하기 위한 프롬프트를 만든다."""
    return _SINGLE_TEMPLATE.format(
        title=article.title,
        body=_article_body(article),
    )


def build_briefing_prompt(articles: list[Article]) -> str:
    """
    같은 사건을 다룬 기사들을 하나로 종합하기 위한 프롬프트를 만든다.

    기사가 하나뿐이면 단일 요약과 다를 바 없으므로 그쪽 프롬프트를 쓴다.
    """
    if len(articles) == 1:
        return build_summary_prompt(articles[0])

    blocks = "\n\n".join(
        _ARTICLE_BLOCK.format(
            index=index,
            source=article.source_name,
            title=article.title,
            body=_article_body(article),
        )
        for index, article in enumerate(articles, start=1)
    )

    return _BRIEFING_TEMPLATE.format(articles=blocks)