# NewsWeaver/src/news_weaver/summarize/ollama.py

"""
로컬 Ollama 서버를 호출해 기사를 요약한다.

모델 추론은 하드웨어에 따라 건당 1~4분이 걸리므로, 한 건의 실패나 지연이
전체 배치를 막지 않도록 기사마다 독립적으로 처리하고 실패를 결과로 담는다.

모델명과 서버 주소는 실행 환경마다 다르므로 설정에서 읽는다.
"""

import logging

import requests

from news_weaver.config import get_settings
from news_weaver.domain.article import Article
from news_weaver.summarize.base import SummaryResult
from news_weaver.summarize.prompt import PROMPT_VERSION, build_summary_prompt

logger = logging.getLogger(__name__)

# CPU 추론 환경에서는 한 건에 수 분이 걸릴 수 있어 넉넉히 잡는다.
# 다만 무한 대기는 배치를 멈추게 하므로 상한은 반드시 둔다
REQUEST_TIMEOUT_SECONDS = 600


class OllamaSummarizer:
    """Ollama HTTP API로 요약을 수행한다."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.ollama_base_url
        self._model_name = model_name or settings.ollama_model

    def summarize(self, articles: list[Article]) -> list[SummaryResult]:
        """기사들을 하나씩 요약한다. 실패한 건은 결과에 이유를 담는다."""
        total = len(articles)
        results: list[SummaryResult] = []

        for index, article in enumerate(articles, start=1):
            # 건당 수십 초가 걸리므로 진행 기록이 없으면 멈춘 것과 구분되지 않는다
            logger.info("요약 %d/%d: %s", index, total, article.title[:40])
            results.append(self._summarize_one(article))

        return results

    def _summarize_one(self, article: Article) -> SummaryResult:
        """기사 하나를 요약한다. 예외는 결과로 변환해 호출자에게 전달한다."""
        try:
            summary_text = self._request_generation(build_summary_prompt(article))
        except requests.RequestException as error:
            logger.warning("요약 요청 실패: %s — %s", article.title[:40], error)
            return self._failure(article, f"요청 실패: {error}")

        if not summary_text:
            logger.warning("요약 응답이 비어 있음: %s", article.title[:40])
            return self._failure(article, "빈 응답")

        return SummaryResult(
            url_hash=article.url_hash,
            summary_text=summary_text,
            model_name=self._model_name,
            prompt_version=PROMPT_VERSION,
        )

    def _request_generation(self, prompt: str) -> str:
        """Ollama에 생성을 요청하고 응답 텍스트를 반환한다."""
        response = requests.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model_name,
                "prompt": prompt,
                "stream": False,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        return response.json().get("response", "").strip()

    def _failure(self, article: Article, reason: str) -> SummaryResult:
        """실패 결과를 만든다."""
        return SummaryResult(
            url_hash=article.url_hash,
            error=reason,
            model_name=self._model_name,
            prompt_version=PROMPT_VERSION,
        )