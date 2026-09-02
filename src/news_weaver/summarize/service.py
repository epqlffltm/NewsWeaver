# NewsWeaver/src/news_weaver/summarize/service.py

"""
캐시를 활용해 기사를 요약하는 흐름을 조립한다.

요약은 건당 수십 초에서 수 분이 걸리므로, 이미 만들어둔 결과가 있으면
모델을 부르지 않는 것이 이 계층의 핵심 책임이다. 배치 재실행이나 실패 후
재시도에서 같은 작업을 반복하지 않게 한다.
"""

from dataclasses import dataclass

from news_weaver.db.summary_repository import SummaryRepository
from news_weaver.domain.article import Article
from news_weaver.summarize.base import Summarizer, SummaryResult


@dataclass(frozen=True, slots=True)
class SummarizedArticle:
    """기사와 그 요약문을 함께 묶은 것. 메일 본문을 만들 때 쓴다."""

    article: Article
    summary_text: str


@dataclass(frozen=True, slots=True)
class SummarizeReport:
    """한 번의 요약 실행 결과와 그 과정을 담는다."""

    summarized: list[SummarizedArticle]

    # 캐시로 처리한 건수. 요약 비용을 얼마나 아꼈는지 보여준다
    cache_hit_count: int

    # 모델을 실제로 호출한 건수
    generated_count: int

    # 요약에 실패한 기사의 제목과 이유. 실패해도 나머지는 전달된다
    failures: list[tuple[str, str]]


def _split_by_cache(
    articles: list[Article],
    cached: dict[str, str],
) -> tuple[list[SummarizedArticle], list[Article]]:
    """기사를 캐시로 해결되는 것과 새로 요약해야 하는 것으로 나눈다."""
    from_cache: list[SummarizedArticle] = []
    to_generate: list[Article] = []

    for article in articles:
        summary_text = cached.get(article.url_hash)
        if summary_text is None:
            to_generate.append(article)
        else:
            from_cache.append(SummarizedArticle(article, summary_text))

    return from_cache, to_generate


def _collect_generated(
    articles: list[Article],
    results: list[SummaryResult],
) -> tuple[list[SummarizedArticle], list[tuple[str, str]]]:
    """요약 결과를 성공과 실패로 나눈다."""
    article_by_hash = {article.url_hash: article for article in articles}

    succeeded: list[SummarizedArticle] = []
    failures: list[tuple[str, str]] = []

    for result in results:
        article = article_by_hash.get(result.url_hash)
        if article is None:
            continue

        if result.is_success:
            succeeded.append(SummarizedArticle(article, result.summary_text))
        else:
            failures.append((article.title, result.error or "알 수 없는 오류"))

    return succeeded, failures


def summarize_with_cache(
    articles: list[Article],
    summarizer: Summarizer,
    repository: SummaryRepository,
    model_name: str,
    prompt_version: str,
) -> SummarizeReport:
    """
    캐시에 없는 기사만 요약하고, 새로 만든 요약은 저장한다.

    모델과 프롬프트가 바뀌면 기존 캐시는 조회되지 않으므로 자동으로
    다시 생성된다. 별도의 무효화 처리가 필요하지 않다.
    """
    url_hashes = [article.url_hash for article in articles]
    cached = repository.find_cached(url_hashes, model_name, prompt_version)

    from_cache, to_generate = _split_by_cache(articles, cached)

    if not to_generate:
        return SummarizeReport(
            summarized=from_cache,
            cache_hit_count=len(from_cache),
            generated_count=0,
            failures=[],
        )

    results = summarizer.summarize(to_generate)
    repository.save_summaries(results)

    generated, failures = _collect_generated(to_generate, results)

    return SummarizeReport(
        summarized=from_cache + generated,
        cache_hit_count=len(from_cache),
        generated_count=len(generated),
        failures=failures,
    )