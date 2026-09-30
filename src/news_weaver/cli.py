# NewsWeaver/src/news_weaver/cli.py

"""
파이프라인을 명령줄에서 실행하는 진입점.

수집 파이프라인은 웹 서버와 무관하게 단독으로 실행 가능해야 하므로,
FastAPI가 아니라 CLI를 기본 진입점으로 둔다. 나중에 웹에서 수동 실행
버튼을 붙이더라도 같은 함수를 호출하는 형태가 된다.
"""

import argparse
import logging
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

from news_weaver.collectors.result import CollectionResult
from news_weaver.collectors.rss_collector import collect_all_feeds
from news_weaver.collectors.sources import RSS_SOURCES
from news_weaver.config import get_settings
from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.delivery_repository import DeliveryRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.db.summary_repository import SummaryRepository
from news_weaver.deliver.base import MailSender
from news_weaver.deliver.history import (
    collect_delivery_contents,
    delivery_date_of,
    exclude_delivered,
    should_skip_delivery,
)
from news_weaver.deliver.render import build_subject, render_digest
from news_weaver.deliver.smtp import SmtpMailSender
from news_weaver.domain.article import Article
from news_weaver.embedding.ollama import OllamaEmbedder
from news_weaver.logging_config import configure_logging
from news_weaver.selection.dedupe import ArticleGroup, group_similar_articles
from news_weaver.selection.interests import INTEREST_TOPICS, MAX_ARTICLES_PER_RUN
from news_weaver.selection.keyword import select_articles
from news_weaver.summarize.ollama import OllamaSummarizer
from news_weaver.summarize.prompt import PROMPT_VERSION
from news_weaver.summarize.service import SummarizeReport, summarize_with_cache

load_dotenv()

logger = logging.getLogger(__name__)

# 배치가 하루 실패해도 그날 기사를 놓치지 않도록 이틀치를 후보로 삼는다.
# 건수로 제한하면 수집량이 늘 때마다 범위가 좁아져 중복 판정이 성립하지 않는다.
# 창이 겹쳐도 이미 보낸 기사는 발송 이력으로 걸러진다
CANDIDATE_WINDOW_DAYS = 2

# 한 번에 임베딩할 상한. 수집 규모가 커져도 배치 시간이 예측 가능하게 한다
EMBEDDING_BATCH_LIMIT = 300

# 여러 기사가 한 사건으로 묶이면 항목 수가 줄어드므로 넉넉히 뽑는다
SELECTION_OVERSAMPLE = 2


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


def embed_pending_articles() -> int:
    """
    아직 벡터가 없는 기사에 임베딩을 생성한다.

    사건 묶기와 유사도 검색이 벡터를 전제하므로 선별보다 먼저 실행한다.
    """
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ArticleRepository(session)
        targets = repository.find_articles_without_embedding(
            settings.embedding_model,
            EMBEDDING_BATCH_LIMIT,
        )

        if not targets:
            return 0

        results = OllamaEmbedder().embed(targets)
        updated_count = repository.save_embeddings(results)
        session.commit()

    failed_count = len([r for r in results if not r.is_success])
    if failed_count:
        logger.warning("임베딩 실패 %d건", failed_count)

    return updated_count


def load_recent_articles(window_days: int) -> list[Article]:
    """
    최근 수집된 기사 중 아직 보내지 않은 것을 선별 후보로 읽어온다.

    후보 창이 하루보다 길어, 이력으로 거르지 않으면 어제 보낸 기사가 다시 실린다.
    """
    since = datetime.now(UTC) - timedelta(days=window_days)
    session_factory = get_session_factory()

    with session_factory() as session:
        articles = ArticleRepository(session).find_recent_articles(since)
        delivered = DeliveryRepository(session).find_delivered_url_hashes(
            [article.url_hash for article in articles]
        )

    return exclude_delivered(articles, delivered)


def has_delivered_today(sent_at: datetime) -> bool:
    """오늘(한국 시간) 이 수신자에게 이미 보냈는지 확인한다."""
    session_factory = get_session_factory()

    with session_factory() as session:
        return DeliveryRepository(session).has_delivered_on(
            delivery_date_of(sent_at),
            get_settings().mail_recipient,
        )


def log_group_composition(group: ArticleGroup) -> None:
    """여러 기사가 묶인 그룹의 구성을 기록한다."""
    if group.size == 1:
        return

    others = ", ".join(item.article.source_name for item in group.others)
    logger.info(
        "사건 묶음 (%d건, %d점): %s ← %s",
        group.size,
        group.score,
        group.representative.article.title[:35],
        others,
    )


def select_and_group(articles: list[Article]) -> list[ArticleGroup]:
    """
    관심 주제로 선별한 뒤 같은 사건을 다룬 기사를 하나로 묶는다.

    묶인 기사를 버리지 않는 이유는 매체마다 강조하는 부분이 달라, 함께
    요약하면 단일 기사보다 정보가 풍부해지기 때문이다.
    """
    settings = get_settings()

    selected = select_articles(
        articles,
        INTEREST_TOPICS,
        MAX_ARTICLES_PER_RUN * SELECTION_OVERSAMPLE,
    )

    if not selected:
        return []

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ArticleRepository(session)
        pairs = repository.find_similarity_pairs(
            [item.article.url_hash for item in selected],
            settings.embedding_model,
            settings.duplicate_similarity_threshold,
        )

    groups = group_similar_articles(selected, pairs)

    for group in groups:
        log_group_composition(group)

    # 보도량을 반영한 점수로 다시 정렬한다. 그룹화 전 순위는 기사 단위
    # 관심도만 반영하므로, 여러 매체가 다룬 사건이 밀려날 수 있다
    groups.sort(key=lambda group: group.score, reverse=True)

    return groups[:MAX_ARTICLES_PER_RUN]


def summarize_selected(groups: list[ArticleGroup]) -> SummarizeReport:
    """선별된 그룹을 캐시를 활용해 요약한다."""
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        report = summarize_with_cache(
            groups,
            OllamaSummarizer(),
            SummaryRepository(session),
            settings.ollama_model,
            PROMPT_VERSION,
        )
        session.commit()

    return report


def deliver_digest(
    report: SummarizeReport,
    sent_at: datetime,
    sender: MailSender | None = None,
) -> str | None:
    """
    요약 결과를 메일로 보내고, 성공하면 제목을 반환한다.

    발송기를 주입받는 이유는 테스트에서 실제 메일을 보내지 않기 위함이다.
    실패나 발송 생략은 None으로 알려, 호출자가 이력을 남기지 않게 한다.
    """
    if not report.summarized:
        logger.info("보낼 요약이 없어 발송을 건너뜁니다.")
        return None

    subject = build_subject(sent_at, len(report.summarized))
    body = render_digest(report.summarized, sent_at)

    result = (sender or SmtpMailSender()).send(subject, body)

    if not result.is_sent:
        logger.error("발송 실패: %s", result.error)
        return None

    logger.info("발송 완료: %s", subject)
    return subject


def record_delivery(report: SummarizeReport, subject: str, sent_at: datetime) -> None:
    """
    발송에 성공한 내용을 이력으로 남긴다.

    발송 전에 기록하면 SMTP 실패 시 보내지도 않은 기사가 다음 실행에서
    제외되므로, 반드시 성공한 뒤에 기록한다.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        DeliveryRepository(session).record_delivery(
            delivery_date_of(sent_at),
            get_settings().mail_recipient,
            subject,
            collect_delivery_contents(report.summarized),
            sent_at,
        )
        session.commit()


def run_ingest(force: bool = False) -> None:
    """
    수집부터 발송까지 한 번의 배치를 실행한다.

    force가 참이면 오늘 이미 보냈더라도 다시 발송한다. 이미 보낸 기사는
    그래도 제외되므로, 그사이 새로 들어온 기사만 실린다.
    """
    configure_logging()

    started_at = datetime.now(UTC)
    logger.info("배치 시작: %s", started_at.isoformat())

    collected = collect_articles(started_at)
    inserted_count = store_articles(collected)
    logger.info("수집 %d건 / 신규 저장 %d건", len(collected), inserted_count)

    embedded_count = embed_pending_articles()
    logger.info("임베딩 생성 %d건", embedded_count)

    # 수집과 임베딩은 재실행해도 무해하므로 먼저 해 두고, 비용이 큰 요약과
    # 발송만 건너뛴다
    if should_skip_delivery(has_delivered_today(started_at), force):
        logger.info("오늘 이미 발송해 건너뜁니다. 다시 보내려면 --force를 쓰세요.")
        return

    candidates = load_recent_articles(CANDIDATE_WINDOW_DAYS)
    selected = select_and_group(candidates)
    logger.info("선별 %d건 (후보 %d건)", len(selected), len(candidates))

    if not selected:
        logger.info("선별된 기사가 없어 배치를 종료합니다.")
        return

    report = summarize_selected(selected)
    logger.info(
        "요약 완료 / 캐시 %d건 / 요청 %d건 / 생성 %d건 / 실패 %d건",
        report.cache_hit_count,
        report.requested_count,
        report.generated_count,
        len(report.failures),
    )

    for failed_title, reason in report.failures:
        logger.warning("요약 실패: %s — %s", failed_title[:40], reason)

    subject = deliver_digest(report, started_at)
    if subject is not None:
        record_delivery(report, subject, started_at)

    logger.info("배치 종료")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """명령줄 인자를 해석한다."""
    parser = argparse.ArgumentParser(description="NewsWeaver 배치를 실행한다.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="오늘 이미 발송했어도 다시 발송한다 (이미 보낸 기사는 제외).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    run_ingest(force=parse_args().force)