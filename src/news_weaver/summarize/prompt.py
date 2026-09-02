# NewsWeaver/src/news_weaver/summarize/prompt.py

"""
요약 프롬프트와 그 버전을 관리한다.

프롬프트는 요약 품질을 좌우하며 자주 수정된다. 수정 시 기존 캐시가 남아
있으면 옛 결과가 그대로 나오므로, 버전을 함께 두어 무효화 근거로 삼는다.

문장 수를 강제하면 원문에 내용이 부족할 때 모델이 없는 내용을 만들어내므로
상한만 둔다. 수치와 고유명사는 요약에서 가장 쉽게 소실되는 정보라 명시적으로
유지를 요구한다.
"""

from news_weaver.domain.article import Article

# 프롬프트를 수정할 때마다 올린다. 요약 캐시의 키 일부로 쓰인다
PROMPT_VERSION = "v1"

_TEMPLATE = """다음 뉴스를 한국어로 3문장 이내로 요약해줘.

규칙:
- 원문에 없는 내용, 평가, 전망을 추가하지 마
- 구체적인 수치와 고유명사는 그대로 유지해
- 요약문만 출력하고 다른 말은 붙이지 마

제목: {title}
본문: {body}"""


def build_summary_prompt(article: Article) -> str:
    """기사 하나를 요약하기 위한 프롬프트를 만든다."""
    body = article.summary or "(본문 없음. 제목만으로 요약)"
    return _TEMPLATE.format(title=article.title, body=body)