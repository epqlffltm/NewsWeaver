# NewsWeaver/tests/test_summarize_service.py

"""
캐시를 활용한 요약 흐름이 중복 호출을 막고 부분 실패를 견디는지 검증한다.
"""

from datetime import UTC, datetime

from news_weaver.domain.article import Article
from news_weaver.summarize.base import SummaryResult
from news_weaver.summarize.fake import FakeSummarizer
from news_weaver.summarize.service import summarize_with_cache

COLLECTED_AT = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)

MODEL_NAME = "fake"
PROMPT_VERSION = "fake-v1"


class InMemorySummaryRepository:
    """
    메모리에만 저장하는 가짜 요약 저장소.

    캐시 동작 검증에 실제 DB가 필요하면 테스트가 느려지고 실행 환경에
    묶이므로, 같은 인터페이스를 가진 최소 구현으로 대체한다.
    """

    def __init__(self) -> None:
        # (url_hash, model_name, prompt_version) -> summary_text
        self._store: dict[tuple[str, str, str], str] = {}

    def find_cached(
        self,
        url_hashes: list[str],
        model_name: str,
        prompt_version: str,
    ) -> dict[str, str]:
        return {
            url_hash: self._store[(url_hash, model_name, prompt_version)]
            for url_hash in url_hashes
            if (url_hash, model_name, prompt_version) in self._store
        }

    def save_summaries(self, results: list[SummaryResult]) -> int:
        saved = 0
        for result in results:
            if not result.is_success:
                continue
            key = (result.url_hash, result.model_name, result.prompt_version)
            if key not in self._store:
                self._store[key] = result.summary_text
                saved += 1
        return saved


class CountingSummarizer:
    """실제로 몇 건을 요약했는지 세는 요약기."""

    def __init__(self, inner: FakeSummarizer) -> None:
        self._inner = inner
        self.called_with_count = 0

    def summarize(self, articles: list[Article]) -> list[SummaryResult]:
        self.called_with_count += len(articles)
        return self._inner.summarize(articles)


def make_article(url_hash: str, title: str = "제목") -> Article:
    """테스트용 기사를 만든다."""
    return Article(
        source_name="테스트",
        title=title,
        url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        collected_at=COLLECTED_AT,
    )


def run(articles, summarizer, repository):
    """반복되는 인자를 묶어 호출한다."""
    return summarize_with_cache(
        articles,
        summarizer,
        repository,
        MODEL_NAME,
        PROMPT_VERSION,
    )


def test_first_run_generates_all() -> None:
    """캐시가 비어 있으면 모든 기사를 요약한다."""
    articles = [make_article("a"), make_article("b")]
    repository = InMemorySummaryRepository()

    report = run(articles, FakeSummarizer(), repository)

    assert report.generated_count == 2
    assert report.cache_hit_count == 0
    assert len(report.summarized) == 2


def test_second_run_uses_cache() -> None:
    """
    같은 조건으로 다시 실행하면 모델을 부르지 않는다.

    배치 재실행이나 실패 후 재시도에서 요약 비용을 다시 치르지 않기 위함이다.
    """
    articles = [make_article("a"), make_article("b")]
    repository = InMemorySummaryRepository()
    run(articles, FakeSummarizer(), repository)

    summarizer = CountingSummarizer(FakeSummarizer())
    report = run(articles, summarizer, repository)

    assert summarizer.called_with_count == 0
    assert report.cache_hit_count == 2
    assert report.generated_count == 0


def test_only_uncached_articles_are_generated() -> None:
    """일부만 캐시에 있으면 나머지만 새로 요약한다."""
    repository = InMemorySummaryRepository()
    run([make_article("a")], FakeSummarizer(), repository)

    summarizer = CountingSummarizer(FakeSummarizer())
    report = run([make_article("a"), make_article("b")], summarizer, repository)

    assert summarizer.called_with_count == 1
    assert report.cache_hit_count == 1
    assert report.generated_count == 1


def test_changed_prompt_version_invalidates_cache() -> None:
    """
    프롬프트가 바뀌면 기존 캐시를 쓰지 않고 다시 요약한다.

    프롬프트를 고쳤는데 옛 요약이 그대로 나오면 변경 효과를 확인할 수 없다.
    """
    articles = [make_article("a")]
    repository = InMemorySummaryRepository()
    run(articles, FakeSummarizer(), repository)

    report = summarize_with_cache(
        articles,
        FakeSummarizer(),
        repository,
        MODEL_NAME,
        "fake-v2",
    )

    assert report.cache_hit_count == 0
    assert report.generated_count == 1


def test_failure_does_not_block_others() -> None:
    """일부가 실패해도 나머지 요약은 전달되고 실패 사유가 남는다."""
    articles = [make_article("a", "정상"), make_article("b", "실패할 기사")]
    summarizer = FakeSummarizer(failing_url_hashes=frozenset({"b"}))

    report = run(articles, summarizer, InMemorySummaryRepository())

    assert len(report.summarized) == 1
    assert len(report.failures) == 1
    assert report.failures[0][0] == "실패할 기사"


def test_failed_article_is_retried_next_run() -> None:
    """
    실패한 기사는 캐시에 남지 않아 다음 실행에서 다시 시도된다.

    일시적 오류로 실패한 기사가 영영 요약되지 않는 상황을 막는다.
    """
    articles = [make_article("a")]
    repository = InMemorySummaryRepository()
    run(articles, FakeSummarizer(failing_url_hashes=frozenset({"a"})), repository)

    report = run(articles, FakeSummarizer(), repository)

    assert report.generated_count == 1
    assert len(report.summarized) == 1


def test_empty_input_returns_empty_report() -> None:
    """선별된 기사가 없으면 아무것도 호출하지 않는다."""
    summarizer = CountingSummarizer(FakeSummarizer())

    report = run([], summarizer, InMemorySummaryRepository())

    assert summarizer.called_with_count == 0
    assert report.summarized == []
    
def test_result_keeps_input_order() -> None:
    """
    캐시 적중 여부가 결과 순서를 바꾸지 않는다.

    입력 순서는 선별 순위이므로, 캐시 때문에 순위가 뒤섞이면
    관련도 높은 기사가 메일 아래로 밀려난다.
    """
    repository = InMemorySummaryRepository()
    run([make_article("b")], FakeSummarizer(), repository)

    articles = [make_article("a"), make_article("b"), make_article("c")]
    report = run(articles, FakeSummarizer(), repository)

    assert [item.article.url_hash for item in report.summarized] == ["a", "b", "c"]