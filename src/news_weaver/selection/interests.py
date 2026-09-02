# NewsWeaver/src/news_weaver/selection/interests.py

"""
수집한 기사 중 어떤 것을 요약할지 정하는 관심 키워드 목록.

지금은 사용자가 한 명이므로 코드 상수로 둔다. 웹에서 키워드를 등록·수정하게
되면 DB 테이블로 옮기지만, 선별 함수는 목록을 인자로 받으므로 영향받지 않는다.
"""

INTEREST_KEYWORDS: tuple[str, ...] = (
    "AI",
    "인공지능",
    "LLM",
    "반도체",
    "클라우드",
    "보안",
)

# 요약은 건당 수십 초가 걸리므로 배치 시간이 예측 가능하도록 상한을 둔다
MAX_ARTICLES_PER_RUN = 10