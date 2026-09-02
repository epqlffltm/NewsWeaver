# NewsWeaver/tests/test_summarize.py

"""
요약 결과 표현과 가짜 요약기가 부분 실패를 올바르게 다루는지 검증한다.
"""

from datetime import UTC, datetime

from news_weaver.domain.article import Article
from news_weaver.summarize.fake import FakeSummarizer

COLLECTED_AT = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def make_article(url_hash: str, title: str = "제목") -> Article:
    """테스트용 기사를 만든다. 요약에 쓰이지 않는 필드는 최소값으로 채운다."""
    return Article(
        source_name="테스트",
        title=title,
        url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        collected_at=COLLECTED_AT,
    )


def test_all_articles_get_a_result() -> None:
    """입력한 기사 수만큼 결과가 나온다."""
    articles = [make_article("a"), make_article("b"), make_article("c")]

    results = FakeSummarizer().summarize(articles)

    assert len(results) == len(articles)


def test_result_is_matched_by_url_hash() -> None:
    """결과에 url_hash가 담겨 어느 기사의 요약인지 식별할 수 있다."""
    articles = [make_article("a"), make_article("b")]

    results = FakeSummarizer().summarize(articles)

    assert {result.url_hash for result in results} == {"a", "b"}


def test_failure_does_not_stop_other_articles() -> None:
    """
    일부가 실패해도 나머지는 요약된다.

    배치에서 한 건의 오류가 전체를 중단시키면 그날 메일이 통째로 나가지 않는다.
    """
    articles = [make_article("a"), make_article("b"), make_article("c")]
    summarizer = FakeSummarizer(failing_url_hashes=frozenset({"b"}))

    results = summarizer.summarize(articles)
    succeeded = [result for result in results if result.is_success]

    assert len(succeeded) == 2
    assert {result.url_hash for result in succeeded} == {"a", "c"}


def test_failed_result_carries_reason() -> None:
    """실패한 결과에는 요약문 대신 이유가 담긴다."""
    summarizer = FakeSummarizer(failing_url_hashes=frozenset({"a"}))

    result = summarizer.summarize([make_article("a")])[0]

    assert result.is_success is False
    assert result.summary_text is None
    assert result.error


def test_result_records_model_and_prompt_version() -> None:
    """
    어떤 모델과 프롬프트로 만든 요약인지 결과에 남는다.

    프롬프트를 고쳤을 때 캐시를 무효화하고 품질 변화를 추적하는 근거가 된다.
    """
    result = FakeSummarizer().summarize([make_article("a")])[0]

    assert result.model_name
    assert result.prompt_version


def test_empty_input_returns_empty_list() -> None:
    """선별된 기사가 없으면 빈 결과를 반환한다."""
    assert FakeSummarizer().summarize([]) == []