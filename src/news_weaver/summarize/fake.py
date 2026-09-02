# NewsWeaver/src/news_weaver/summarize/fake.py

"""
테스트용 가짜 요약기.

실제 모델 호출은 건당 1~2분이 걸려 테스트에서 쓸 수 없다. 요약 자체가 아니라
그 결과를 다루는 파이프라인 로직을 검증하기 위해 즉시 응답하는 구현을 둔다.
"""

from news_weaver.domain.article import Article
from news_weaver.summarize.base import SummaryResult

FAKE_MODEL_NAME = "fake"
FAKE_PROMPT_VERSION = "fake-v1"


class FakeSummarizer:
    """제목을 그대로 돌려주는 요약기. 실패를 재현할 수도 있다."""

    def __init__(self, failing_url_hashes: frozenset[str] = frozenset()) -> None:
        # 부분 실패 처리를 검증하려면 일부러 실패시킬 수단이 필요하다
        self._failing_url_hashes = failing_url_hashes

    def summarize(self, articles: list[Article]) -> list[SummaryResult]:
        """각 기사에 대해 즉시 결과를 만들어 반환한다."""
        return [self._summarize_one(article) for article in articles]

    def _summarize_one(self, article: Article) -> SummaryResult:
        """기사 하나에 대한 결과를 만든다."""
        if article.url_hash in self._failing_url_hashes:
            return SummaryResult(
                url_hash=article.url_hash,
                error="의도적으로 실패시킨 항목",
                model_name=FAKE_MODEL_NAME,
                prompt_version=FAKE_PROMPT_VERSION,
            )

        return SummaryResult(
            url_hash=article.url_hash,
            summary_text=f"[요약] {article.title}",
            model_name=FAKE_MODEL_NAME,
            prompt_version=FAKE_PROMPT_VERSION,
        )