# NewsWeaver/src/news_weaver/cli.py

"""
파이프라인을 명령줄에서 실행하는 진입점.

수집 파이프라인은 웹 서버와 무관하게 단독으로 실행 가능해야 하므로,
FastAPI가 아니라 CLI를 기본 진입점으로 둔다. 나중에 웹에서 수동 실행
버튼을 붙이더라도 같은 함수를 호출하는 형태가 된다.
"""

from datetime import UTC, datetime

from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.collectors.result import CollectionResult
from news_weaver.collectors.rss_collector import collect_all_feeds
from news_weaver.collectors.sources import RSS_SOURCES
from news_weaver.config import get_settings
from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.db.summary_repository import SummaryRepository
from news_weaver.db.tables import ArticleRow
from news_weaver.deliver.render import build_subject, render_digest
from news_weaver.deliver.smtp import SmtpMailSender
from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS, MAX_ARTICLES_PER_RUN
from news_weaver.selection.keyword import select_articles
from news_weaver.summarize.ollama import OllamaSummarizer
from news_weaver.summarize.prompt import PROMPT_VERSION
from news_weaver.summarize.service import SummarizeReport, summarize_with_cache

load_dotenv()

# 오래된 기사를 다시 요약하지 않도록, 선별 대상을 최근 수집분으로 제한한다
RECENT_ARTICLE_LIMIT = 200


def print_source_report(result: CollectionResult) -> None:
    """소스 하나의 수집 결과를 한 줄로 출력한다."""
    status = "정상" if result.is_healthy else "장애"
    line = f"[{status}] {result.source_name:12} 수집 {result.article_count:3}건"

    if result.skipped_count:
        line += f" / 버림 {result.skipped_count}건"

    if result.error:
        line += f" / 원인: {result.error}"

    print(line)


def collect_articles(collected_at: datetime) -> list[Article]:
    """모든 소스를 수집하고 결과를 출력한 뒤, 기사들을 한 목록으로 모은다."""
    results = collect_all_feeds(RSS_SOURCES, collected_at)

    articles: list[Article] = []
    for result in results:
        print_source_report(result)
        articles.extend(result.articles)

    unhealthy_sources = [r.source_name for r in results if not r.is_healthy]
    if unhealthy_sources:
        print(f"장애 소스: {', '.join(unhealthy_sources)}")

    return articles


def store_articles(articles: list[Article]) -> int:
    """기사들을 저장하고 새로 삽입된 건수를 반환한다."""
    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ArticleRepository(session)
        inserted_count = repository.save_articles(articles)
        session.commit()

    return inserted_count


def load_recent_articles(limit: int) -> list[Article]:
    """
    최근 수집된 기사를 읽어온다.

    선별 대상을 최근 분량으로 제한해, 오래된 기사가 매일 다시 후보에
    오르지 않게 한다.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        rows = (
            session.execute(
                select(ArticleRow)
                .order_by(ArticleRow.collected_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    return [
        Article(
            source_name=row.source_name,
            title=row.title,
            url=row.url,
            url_hash=row.url_hash,
            collected_at=row.collected_at,
            published_at=row.published_at,
            author=row.author,
            summary=row.summary,
        )
        for row in rows
    ]


def summarize_selected(articles: list[Article]) -> SummarizeReport:
    """선별된 기사를 캐시를 활용해 요약한다."""
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        report = summarize_with_cache(
            articles,
            OllamaSummarizer(),
            SummaryRepository(session),
            settings.ollama_model,
            PROMPT_VERSION,
        )
        session.commit()

    return report


def deliver_digest(report: SummarizeReport, sent_at: datetime) -> None:
    """요약 결과를 메일로 보낸다."""
    if not report.summarized:
        print("보낼 요약이 없어 발송을 건너뜁니다.")
        return

    subject = build_subject(sent_at, len(report.summarized))
    body = render_digest(report.summarized, sent_at)

    result = SmtpMailSender().send(subject, body)

    if result.is_sent:
        print(f"발송 완료: {subject}")
    else:
        print(f"발송 실패: {result.error}")


def run_ingest() -> None:
    """수집부터 발송까지 한 번의 배치를 실행한다."""
    started_at = datetime.now(UTC)
    print(f"실행 시각: {started_at.isoformat()}\n")

    collected = collect_articles(started_at)
    inserted_count = store_articles(collected)
    print(f"\n수집 {len(collected)}건 / 신규 저장 {inserted_count}건")

    candidates = load_recent_articles(RECENT_ARTICLE_LIMIT)
    selected = select_articles(candidates, INTEREST_TOPICS, MAX_ARTICLES_PER_RUN)
    print(f"선별 {len(selected)}건 (후보 {len(candidates)}건)")

    if not selected:
        print("선별된 기사가 없습니다.")
        return

    report = summarize_selected([item.article for item in selected])
    print(f"요약 완료 / 캐시 {report.cache_hit_count}건 ")
    print(f"/ 생성 {report.generated_count}건 / 실패 {len(report.failures)}건")

    for failed_title, reason in report.failures:
        print(f"  실패: {failed_title[:40]} — {reason}")

    deliver_digest(report, started_at)


if __name__ == "__main__":
    run_ingest()