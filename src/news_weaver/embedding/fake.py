# NewsWeaver/src/news_weaver/embedding/fake.py

"""
테스트용 가짜 임베딩 생성기.

실제 모델 호출은 느리고 실행 환경에 묶이므로, 임베딩 자체가 아니라 그
결과를 다루는 파이프라인 로직을 검증하기 위해 즉시 응답하는 구현을 둔다.

같은 입력에 항상 같은 벡터를 돌려주어야 테스트 결과가 흔들리지 않는다.
"""

import hashlib

from news_weaver.domain.article import Article
from news_weaver.embedding.base import EmbeddingResult, build_embedding_text

FAKE_MODEL_NAME = "fake-embedder"
FAKE_DIMENSION = 768


def _text_to_vector(text: str, dimension: int) -> list[float]:
    """텍스트에서 결정적인 벡터를 만든다. 같은 텍스트는 같은 벡터가 된다."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()

    return [digest[index % len(digest)] / 255.0 for index in range(dimension)]


class FakeEmbedder:
    """텍스트 해시로 만든 벡터를 돌려준다. 실패를 재현할 수도 있다."""

    def __init__(self, failing_url_hashes: frozenset[str] = frozenset()) -> None:
        # 부분 실패 처리를 검증하려면 일부러 실패시킬 수단이 필요하다
        self._failing_url_hashes = failing_url_hashes

    def embed(self, articles: list[Article]) -> list[EmbeddingResult]:
        """각 기사에 대해 즉시 결과를 만들어 반환한다."""
        return [self._embed_one(article) for article in articles]

    def _embed_one(self, article: Article) -> EmbeddingResult:
        """기사 하나에 대한 결과를 만든다."""
        if article.url_hash in self._failing_url_hashes:
            return EmbeddingResult(
                url_hash=article.url_hash,
                error="의도적으로 실패시킨 항목",
                model_name=FAKE_MODEL_NAME,
            )

        return EmbeddingResult(
            url_hash=article.url_hash,
            vector=_text_to_vector(build_embedding_text(article), FAKE_DIMENSION),
            model_name=FAKE_MODEL_NAME,
        )