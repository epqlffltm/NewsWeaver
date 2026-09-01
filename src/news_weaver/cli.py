# NewsWeaver/src/news_weaver/cli.py

"""
파이프라인을 명령줄에서 실행하는 진입점.

수집 파이프라인은 웹 서버와 무관하게 단독으로 실행 가능해야 하므로,
FastAPI가 아니라 CLI를 기본 진입점으로 둔다. 나중에 웹에서 수동 실행
버튼을 붙이더라도 같은 함수를 호출하는 형태가 된다.
"""

from datetime import UTC, datetime

from news_weaver.collectors.result import CollectionResult
from news_weaver.collectors.rss_collector import collect_all_feeds
from news_weaver.collectors.sources import RSS_SOURCES


def print_source_report(result: CollectionResult) -> None:
    """소스 하나의 수집 결과를 한 줄로 출력한다."""
    status = "정상" if result.is_healthy else "장애"
    line = f"[{status}] {result.source_name:12} 수집 {result.article_count:3}건"

    if result.skipped_count:
        line += f" / 버림 {result.skipped_count}건"

    if result.error:
        line += f" / 원인: {result.error}"

    print(line)


def print_article_samples(result: CollectionResult, sample_count: int = 2) -> None:
    """수집된 기사 중 몇 건을 상세히 출력한다."""
    for article in result.articles[:sample_count]:
        print(f"    제목   : {article.title[:50]}")
        print(f"    발행   : {article.published_at}")
        print(f"    작성자 : {article.author}")
        print(f"    요약   : {str(article.summary)[:60]}")
        print(f"    해시   : {article.url_hash[:16]}...")
        print()


def run_ingest() -> None:
    """전체 소스를 수집하고 결과를 콘솔에 출력한다."""
    collected_at = datetime.now(UTC)

    print(f"수집 시각: {collected_at.isoformat()}\n")

    results = collect_all_feeds(RSS_SOURCES, collected_at)

    for result in results:
        print_source_report(result)
        print_article_samples(result)

    total_articles = sum(result.article_count for result in results)
    unhealthy_sources = [r.source_name for r in results if not r.is_healthy]

    print(f"{'=' * 60}")
    print(f"총 수집: {total_articles}건 / 소스 {len(results)}개")

    if unhealthy_sources:
        print(f"장애 소스: {', '.join(unhealthy_sources)}")


if __name__ == "__main__":
    run_ingest()