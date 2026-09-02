# NewsWeaver/src/news_weaver/embedding/ollama.py

"""
로컬 Ollama 서버를 호출해 기사 임베딩을 생성한다.

임베딩은 수집한 기사 전부에 적용되어 요약보다 건수가 훨씬 많으므로,
건당 지연이 배치 시간에 크게 반영된다. 다만 한 건의 실패가 나머지를
막지 않도록 기사마다 독립적으로 처리한다.
"""

import logging

import requests

from news_weaver.config import get_settings
from news_weaver.domain.article import Article
from news_weaver.embedding.base import EmbeddingResult, build_embedding_text

logger = logging.getLogger(__name__)

# 임베딩은 생성보다 훨씬 빠르므로 요약보다 짧게 잡는다
REQUEST_TIMEOUT_SECONDS = 120

# 진행 상황을 남길 간격. 매 건마다 남기면 로그가 지나치게 길어진다
PROGRESS_LOG_INTERVAL = 20


class OllamaEmbedder:
    """Ollama HTTP API로 임베딩을 생성한다."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.ollama_base_url
        self._model_name = model_name or settings.embedding_model

    def embed(self, articles: list[Article]) -> list[EmbeddingResult]:
        """기사들을 하나씩 벡터로 변환한다."""
        total = len(articles)
        results: list[EmbeddingResult] = []

        for index, article in enumerate(articles, start=1):
            if index % PROGRESS_LOG_INTERVAL == 0:
                logger.info("임베딩 %d/%d", index, total)
            results.append(self._embed_one(article))

        return results

    def _embed_one(self, article: Article) -> EmbeddingResult:
        """기사 하나를 벡터로 변환한다. 예외는 결과로 변환한다."""
        try:
            vector = self._request_embedding(build_embedding_text(article))
        except requests.RequestException as error:
            logger.warning("임베딩 요청 실패: %s — %s", article.title[:40], error)
            return EmbeddingResult(
                url_hash=article.url_hash,
                error=f"요청 실패: {error}",
                model_name=self._model_name,
            )

        return EmbeddingResult(
            url_hash=article.url_hash,
            vector=vector,
            model_name=self._model_name,
        )

    def _request_embedding(self, text: str) -> list[float]:
        """Ollama에 임베딩을 요청하고 벡터를 반환한다."""
        response = requests.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model_name, "input": text},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        return response.json()["embeddings"][0]