# NewsWeaver/src/news_weaver/summarize/base.py

"""
요약기가 지켜야 할 인터페이스와 요약 결과 표현.

실제 요약은 모델 호출에 건당 수십 초가 걸리므로 테스트에서 부를 수 없다.
이 프로토콜은 테스트에서 가짜 구현으로 대체하기 위해 존재하며,
모델 교체 가능성은 부수적인 이득이다.

한 건의 실패가 나머지를 막지 않도록 실패도 결과값으로 표현한다.
"""

from dataclasses import dataclass
from typing import Protocol

from news_weaver.domain.article import Article


@dataclass(frozen=True, slots=True)
class SummaryResult:
    """기사 한 건에 대한 요약 시도의 결과."""

    url_hash: str

    # 성공했을 때만 채워진다. 실패한 건은 None이며 error에 이유가 담긴다
    summary_text: str | None = None
    error: str | None = None

    # 어떤 모델과 프롬프트로 만들었는지. 캐시 무효화와 품질 추적에 쓴다
    model_name: str = ""
    prompt_version: str = ""

    @property
    def is_success(self) -> bool:
        """요약에 성공했는지 여부."""
        return self.summary_text is not None


class Summarizer(Protocol):
    """
    기사 목록을 요약하는 구현이 지켜야 할 인터페이스.

    단건이 아니라 목록을 받는다. 구현체가 내부에서 병렬 처리나 배치 호출을
    선택할 수 있도록 하기 위함이며, 호출자는 그 차이를 알 필요가 없다.
    """

    def summarize(self, articles: list[Article]) -> list[SummaryResult]:
        """
        기사들을 요약한다.

        일부가 실패해도 예외를 던지지 않고, 실패 사실을 담은 결과를 포함해
        반환한다. 배치에서 한 건의 오류가 전체를 중단시키면 안 되기 때문이다.
        """
        ...