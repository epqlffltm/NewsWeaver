# NewsWeaver/src/news_weaver/selection/interests.py

"""
수집한 기사 중 어떤 것을 요약할지 정하는 관심 주제 목록.

같은 개념이 여러 표현으로 등장하므로(예: "인공지능(AI)" 병기) 표현 단위가
아니라 주제 단위로 점수를 매긴다. 그러지 않으면 병기 관습이 있는 주제만
점수가 부풀어 상위를 독점한다.

지금은 사용자가 한 명이므로 코드 상수로 둔다. 웹에서 주제를 등록·수정하게
되면 DB 테이블로 옮기지만, 선별 함수는 목록을 인자로 받으므로 영향받지 않는다.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Topic:
    """하나의 관심 주제와 그것을 가리키는 표현들."""

    name: str

    # 이 주제를 가리키는 표현. 하나라도 걸리면 주제가 매칭된 것으로 본다
    expressions: tuple[str, ...]


INTEREST_TOPICS: tuple[Topic, ...] = (
    Topic("AI", ("AI", "인공지능")),
    Topic("LLM", ("LLM", "거대언어모델", "언어모델")),
    Topic("반도체", ("반도체", "파운드리")),
    Topic("클라우드", ("클라우드", "CSP")),
    Topic("보안", ("보안", "해킹", "취약점")),
)

# 요약은 건당 수십 초가 걸리므로 배치 시간이 예측 가능하도록 상한을 둔다
MAX_ARTICLES_PER_RUN = 10