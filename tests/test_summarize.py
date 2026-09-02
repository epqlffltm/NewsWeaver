# NewsWeaver/tests/test_summarize.py

"""
요약 결과 표현과 가짜 요약기가 부분 실패를 올바르게 다루는지 검증한다.
"""

from datetime import UTC, datetime

from news_weaver.domain.article import Article
from news_weaver.selection.dedupe import ArticleGroup
from news_weaver.selection.keyword import ScoredArticle
from news_weaver.summarize.fake import FakeSummarizer

COLLECTED_AT = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def make_group(url_hash: str, title: str = "제목") -> ArticleGroup:
    """구성원이 하나인 테스트용 그룹을 만든다."""
    article = Article(
        source_name="테스트",
        title=title,
        url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        collected_at=COLLECTED_AT,
    )
    scored = ScoredArticle(article=article, score=9, matched_topics=("AI",))

    return ArticleGroup(representative=scored)


def test_all_groups_get_a_result() -> None:
    """입력한 그룹 수만큼 결과가 나온다."""
    groups = [make_group("a"), make_group("b"), make_group("c")]

    results = FakeSummarizer().summarize(groups)

    assert len(results) == len(groups)


def test_result_is_matched_by_content_key() -> None:
    """결과에 content_key가 담겨 어느 그룹의 요약인지 식별할 수 있다."""
    groups = [make_group("a"), make_group("b")]

    results = FakeSummarizer().summarize(groups)

    assert {r.content_key for r in results} == {g.group_key for g in groups}


def test_failure_does_not_stop_other_groups() -> None:
    """
    일부가 실패해도 나머지는 요약된다.

    배치에서 한 건의 오류가 전체를 중단시키면 그날 메일이 통째로 나가지 않는다.
    """
    groups = [make_group("a"), make_group("b"), make_group("c")]
    summarizer = FakeSummarizer(
        failing_content_keys=frozenset({groups[1].group_key})
    )

    results = summarizer.summarize(groups)
    succeeded = [result for result in results if result.is_success]

    assert len(succeeded) == 2


def test_failed_result_carries_reason() -> None:
    """실패한 결과에는 요약문 대신 이유가 담긴다."""
    group = make_group("a")
    summarizer = FakeSummarizer(failing_content_keys=frozenset({group.group_key}))

    result = summarizer.summarize([group])[0]

    assert result.is_success is False
    assert result.summary_text is None
    assert result.error


def test_result_records_model_and_prompt_version() -> None:
    """
    어떤 모델과 프롬프트로 만든 요약인지 결과에 남는다.

    프롬프트를 고쳤을 때 캐시를 무효화하고 품질 변화를 추적하는 근거가 된다.
    """
    result = FakeSummarizer().summarize([make_group("a")])[0]

    assert result.model_name
    assert result.prompt_version


def test_empty_input_returns_empty_list() -> None:
    """선별된 그룹이 없으면 빈 결과를 반환한다."""
    assert FakeSummarizer().summarize([]) == []