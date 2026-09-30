# NewsWeaver/tests/test_delivery_history.py

"""
발송 이력으로 중복 발송을 막는 판단 로직을 DB 없이 검증한다.
"""

from datetime import UTC, date, datetime

from news_weaver.cli import deliver_digest
from news_weaver.deliver.fake import FakeMailSender
from news_weaver.deliver.history import (
    collect_delivery_contents,
    delivery_date_of,
    exclude_delivered,
    should_skip_delivery,
)
from news_weaver.domain.article import Article
from news_weaver.selection.dedupe import ArticleGroup
from news_weaver.selection.keyword import ScoredArticle
from news_weaver.summarize.service import SummarizedGroup, SummarizeReport

COLLECTED_AT = datetime(2026, 9, 2, 6, 0, tzinfo=UTC)
SENT_AT = datetime(2026, 9, 2, 7, 0, tzinfo=UTC)


def make_article(url_hash: str) -> Article:
    """테스트용 기사를 만든다."""
    return Article(
        source_name="테스트",
        title=f"제목-{url_hash}",
        url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        collected_at=COLLECTED_AT,
    )


def make_summarized(*url_hashes: str) -> SummarizedGroup:
    """첫 기사를 대표로 하는 요약 결과를 만든다."""
    scored = [
        ScoredArticle(article=make_article(h), score=5, matched_topics=("AI",))
        for h in url_hashes
    ]
    group = ArticleGroup(representative=scored[0], others=tuple(scored[1:]))
    return SummarizedGroup(group, "요약문")


def make_report(summarized: list[SummarizedGroup]) -> SummarizeReport:
    """테스트용 요약 보고서를 만든다."""
    return SummarizeReport(
        summarized=summarized,
        cache_hit_count=0,
        requested_count=len(summarized),
        generated_count=len(summarized),
        failures=[],
    )


def test_delivery_date_uses_korean_time() -> None:
    """
    같은 날의 기준은 한국 시간이다.

    UTC 날짜를 쓰면 한국 오전 9시를 경계로 날짜가 바뀌어, 아침 배치와
    그 직후 재실행이 다른 날로 취급된다.
    """
    before_kst_nine = datetime(2026, 9, 1, 22, 0, tzinfo=UTC)  # KST 9/2 07:00
    after_kst_nine = datetime(2026, 9, 2, 1, 0, tzinfo=UTC)  # KST 9/2 10:00

    assert delivery_date_of(before_kst_nine) == date(2026, 9, 2)
    assert delivery_date_of(after_kst_nine) == date(2026, 9, 2)


def test_skip_when_already_delivered_today() -> None:
    """오늘 이미 보냈으면 건너뛴다."""
    assert should_skip_delivery(already_delivered_today=True, force=False) is True


def test_force_overrides_same_day_skip() -> None:
    """강제 실행이면 오늘 보냈어도 진행한다."""
    assert should_skip_delivery(already_delivered_today=True, force=True) is False


def test_first_delivery_of_day_proceeds() -> None:
    """오늘 처음이면 진행한다."""
    assert should_skip_delivery(already_delivered_today=False, force=False) is False


def test_exclude_delivered_removes_sent_articles_keeping_order() -> None:
    """이전에 보낸 기사는 빠지고 나머지는 순서를 유지한다."""
    articles = [make_article(h) for h in ("a", "b", "c", "d")]

    remaining = exclude_delivered(articles, {"b", "d"})

    assert [article.url_hash for article in remaining] == ["a", "c"]


def test_exclude_delivered_with_no_history_keeps_all() -> None:
    """이력이 없으면 모두 후보로 남는다."""
    articles = [make_article(h) for h in ("a", "b")]

    assert exclude_delivered(articles, set()) == articles


def test_contents_include_every_group_member() -> None:
    """
    대표뿐 아니라 그룹의 모든 기사를 기록한다.

    묶여서 함께 나간 기사도 다음 날 다시 실리면 안 되기 때문이다.
    """
    single = make_summarized("a")
    grouped = make_summarized("b", "c")

    contents = collect_delivery_contents([single, grouped])

    assert contents.content_keys == (single.group.group_key, grouped.group.group_key)
    assert contents.url_hashes == ("a", "b", "c")


def test_deliver_digest_returns_subject_on_success() -> None:
    """발송에 성공하면 제목을 돌려주어 호출자가 이력을 남길 수 있게 한다."""
    sender = FakeMailSender()

    subject = deliver_digest(make_report([make_summarized("a")]), SENT_AT, sender)

    assert subject is not None
    assert sender.send_count == 1
    assert sender.sent_subject == subject


def test_deliver_digest_returns_none_on_failure() -> None:
    """
    발송에 실패하면 None을 돌려준다.

    실패를 기록하면 보내지도 않은 기사가 다음 실행에서 제외된다.
    """
    sender = FakeMailSender(should_fail=True)

    subject = deliver_digest(make_report([make_summarized("a")]), SENT_AT, sender)

    assert subject is None
    assert sender.send_count == 1


def test_deliver_digest_skips_empty_report() -> None:
    """보낼 요약이 없으면 발송기를 부르지 않는다."""
    sender = FakeMailSender()

    assert deliver_digest(make_report([]), SENT_AT, sender) is None
    assert sender.send_count == 0
