# NewsWeaver/src/news_weaver/cli.py

"""
파이프라인을 명령줄에서 실행하는 진입점.

수집 파이프라인은 웹 서버와 무관하게 단독으로 실행 가능해야 하므로,
FastAPI가 아니라 CLI를 기본 진입점으로 둔다. 나중에 웹에서 수동 실행
버튼을 붙이더라도 같은 함수를 호출하는 형태가 된다.
"""

import logging
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
from news_weaver.logging_config import configure_logging
from news_weaver.selection.interests import INTEREST_TOPICS, MAX_ARTICLES_PER_RUN
from news_weaver.selection.keyword import select_articles
from news_weaver.summarize.ollama import OllamaSummarizer
from news_weaver.summarize.prompt import PROMPT_VERSION
from news_weaver.summarize.service import SummarizeReport, summarize_with_cache

load_dotenv()

logger = logging.getLogger(__name__)

# 오래된 기사가 매일 다시 후보에 오르지 않도록 선별 대상을 최근 수집분으로 제한한다
RECENT_ARTICLE_LIMIT = 200


def log_source_report(result: CollectionResult) -> None:
    """소스 하나의 수집 결과를 한 줄로 기록한다."""
    status = "정상" if result.is_healthy else "장애"
    line = f"[{status}] {result.source_name:12} 수집 {result.article_count:3}건"

    if result.skipped_count:
        line += f" / 버림 {result.skipped_count}건"

    if result.error:
        line += f" / 원인: {result.error}"

    logger.info(line)


def collect_articles(collected_at: datetime) -> list[Article]:
    """모든 소스를 수집하고 결과를 기록한 뒤, 기사들을 한 목록으로 모은다."""
    results = collect_all_feeds(RSS_SOURCES, collected_at)

    articles: list[Article] = []
    for result in results:
        log_source_report(result)
        articles.extend(result.articles)

    unhealthy_sources = [r.source_name for r in results if not r.is_healthy]
    if unhealthy_sources:
        logger.warning("장애 소스: %s", ", ".join(unhealthy_sources))

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
        logger.info("보낼 요약이 없어 발송을 건너뜁니다.")
        return

    subject = build_subject(sent_at, len(report.summarized))
    body = render_digest(report.summarized, sent_at)

    result = SmtpMailSender().send(subject, body)

    if result.is_sent:
        logger.info("발송 완료: %s", subject)
    else:
        logger.error("발송 실패: %s", result.error)


def run_ingest() -> None:
    """수집부터 발송까지 한 번의 배치를 실행한다."""
    configure_logging()

    started_at = datetime.now(UTC)
    logger.info("배치 시작: %s", started_at.isoformat())

    collected = collect_articles(started_at)
    inserted_count = store_articles(collected)
    logger.info("수집 %d건 / 신규 저장 %d건", len(collected), inserted_count)

    candidates = load_recent_articles(RECENT_ARTICLE_LIMIT)
    selected = select_articles(candidates, INTEREST_TOPICS, MAX_ARTICLES_PER_RUN)
    logger.info("선별 %d건 (후보 %d건)", len(selected), len(candidates))

    if not selected:
        logger.info("선별된 기사가 없어 배치를 종료합니다.")
        return

    report = summarize_selected([item.article for item in selected])
    logger.info(
        "요약 완료 / 캐시 %d건 / 생성 %d건 / 실패 %d건",
        report.cache_hit_count,
        report.generated_count,
        len(report.failures),
    )

    for failed_title, reason in report.failures:
        logger.warning("요약 실패: %s — %s", failed_title[:40], reason)

    deliver_digest(report, started_at)
    logger.info("배치 종료")


if __name__ == "__main__":
    run_ingest()