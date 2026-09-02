# NewsWeaver/src/news_weaver/summarize/service.py

"""
캐시를 활용해 기사 그룹을 요약하는 흐름을 조립한다.

요약은 건당 수십 초에서 수 분이 걸리므로, 이미 만들어둔 결과가 있으면
모델을 부르지 않는 것이 이 계층의 핵심 책임이다. 배치 재실행이나 실패 후
재시도에서 같은 작업을 반복하지 않게 한다.

캐시 적중 여부는 요약 순서에 영향을 주면 안 된다. 입력으로 받은 선별 순위가
관련도를 나타내므로, 결과도 그 순서를 그대로 유지한다.
"""

from dataclasses import dataclass

from news_weaver.db.summary_repository import SummaryRepository
from news_weaver.selection.dedupe import ArticleGroup
from news_weaver.summarize.base import Summarizer, SummaryResult


@dataclass(frozen=True, slots=True)
class SummarizedGroup:
    """기사 그룹과 그 요약문을 함께 묶은 것. 메일 본문을 만들 때 쓴다."""

    group: ArticleGroup
    summary_text: str


@dataclass(frozen=True, slots=True)
class SummarizeReport:
    """한 번의 요약 실행 결과와 그 과정을 담는다."""

    # 입력으로 받은 선별 순서를 그대로 유지한다
    summarized: list[SummarizedGroup]

    # 캐시로 처리한 건수. 요약 비용을 얼마나 아꼈는지 보여준다
    cache_hit_count: int

    # 모델에 실제로 넘긴 건수. 실패분을 포함하므로 비용 추정의 근거가 된다
    requested_count: int

    # 그중 요약문을 얻은 건수
    generated_count: int

    # 요약에 실패한 대표 기사의 제목과 이유. 실패해도 나머지는 전달된다
    failures: list[tuple[str, str]]


def _split_by_cache(
    groups: list[ArticleGroup],
    cached: dict[str, str],
) -> list[ArticleGroup]:
    """캐시에 없어 새로 요약해야 하는 그룹만 골라낸다."""
    return [group for group in groups if group.group_key not in cached]


def _index_results(results: list[SummaryResult]) -> dict[str, SummaryResult]:
    """결과를 content_key로 찾을 수 있게 사전으로 만든다."""
    return {result.content_key: result for result in results}


def _collect_failures(
    groups: list[ArticleGroup],
    results_by_key: dict[str, SummaryResult],
) -> list[tuple[str, str]]:
    """요약에 실패한 그룹의 대표 제목과 이유를 모은다."""
    failures: list[tuple[str, str]] = []

    for group in groups:
        result = results_by_key.get(group.group_key)
        if result is not None and not result.is_success:
            failures.append(
                (group.representative.article.title, result.error or "알 수 없는 오류")
            )

    return failures


def _build_summarized(
    groups: list[ArticleGroup],
    cached: dict[str, str],
    results_by_key: dict[str, SummaryResult],
) -> list[SummarizedGroup]:
    """
    입력 순서를 유지한 채 요약문을 붙인다.

    캐시에서 온 것과 새로 만든 것을 나눠 이어붙이면 선별 순위가 뒤섞이므로,
    원본 목록을 한 번 순회하며 조립한다.
    """
    summarized: list[SummarizedGroup] = []

    for group in groups:
        summary_text = cached.get(group.group_key)

        if summary_text is None:
            result = results_by_key.get(group.group_key)
            if result is None or not result.is_success:
                continue
            summary_text = result.summary_text

        summarized.append(SummarizedGroup(group, summary_text))

    return summarized


def summarize_with_cache(
    groups: list[ArticleGroup],
    summarizer: Summarizer,
    repository: SummaryRepository,
    model_name: str,
    prompt_version: str,
) -> SummarizeReport:
    """
    캐시에 없는 그룹만 요약하고, 새로 만든 요약은 저장한다.

    모델과 프롬프트가 바뀌면 기존 캐시는 조회되지 않으므로 자동으로
    다시 생성된다. 그룹 구성이 바뀌어도 키가 달라져 마찬가지로 재생성된다.
    """
    content_keys = [group.group_key for group in groups]
    cached = repository.find_cached(content_keys, model_name, prompt_version)

    to_generate = _split_by_cache(groups, cached)

    results_by_key: dict[str, SummaryResult] = {}
    if to_generate:
        results = summarizer.summarize(to_generate)
        repository.save_summaries(results)
        results_by_key = _index_results(results)

    summarized = _build_summarized(groups, cached, results_by_key)
    failures = _collect_failures(to_generate, results_by_key)

    return SummarizeReport(
        summarized=summarized,
        cache_hit_count=len(cached),
        requested_count=len(to_generate),
        generated_count=len(summarized) - len(cached),
        failures=failures,
    )