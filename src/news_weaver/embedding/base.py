# NewsWeaver/src/news_weaver/embedding/base.py

"""
임베딩 생성기가 지켜야 할 인터페이스와 결과 표현.

테스트에서 실제 모델을 부르면 느리고 실행 환경에 묶이므로, 가짜 구현으로
대체하기 위해 프로토콜을 둔다.

임베딩 대상은 수집한 기사 전부라 건수가 많고, 한 건의 실패가 나머지를
막으면 안 되므로 실패도 결과값으로 표현한다.
"""

from dataclasses import dataclass
from typing import Protocol

from news_weaver.domain.article import Article


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """기사 한 건에 대한 임베딩 시도의 결과."""

    url_hash: str

    # 성공했을 때만 채워진다. 실패한 건은 None이며 error에 이유가 담긴다
    vector: list[float] | None = None
    error: str | None = None

    # 어떤 모델로 만든 벡터인지. 벡터 공간이 다르면 유사도가 무의미하므로
    # 모델 교체 시 재생성 대상을 골라내는 근거가 된다
    model_name: str = ""

    @property
    def is_success(self) -> bool:
        """임베딩에 성공했는지 여부."""
        return self.vector is not None


def build_embedding_text(article: Article) -> str:
    """
    임베딩할 텍스트를 만든다.

    제목만으로는 의미가 빈약하고, 요약을 제공하지 않는 소스가 있으므로
    둘을 합치되 없는 쪽은 건너뛴다.
    """
    if article.summary:
        return f"{article.title}\n{article.summary}"
    return article.title


class Embedder(Protocol):
    """기사를 벡터로 변환하는 구현이 지켜야 할 인터페이스."""

    def embed(self, articles: list[Article]) -> list[EmbeddingResult]:
        """
        기사들을 벡터로 변환한다.

        일부가 실패해도 예외를 던지지 않고, 실패 사실을 담은 결과를 포함해
        반환한다. 배치에서 한 건의 오류가 전체를 중단시키면 안 되기 때문이다.
        """
        ...