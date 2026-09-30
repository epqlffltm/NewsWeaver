# NewsWeaver/src/news_weaver/deliver/history.py

"""
발송 이력을 바탕으로 무엇을 보내고 무엇을 건너뛸지 판단한다.

선별 후보는 최근 며칠치를 보므로, 이력이 없으면 어제 보낸 기사가 오늘
다시 실리고 같은 날 재실행하면 메일이 두 번 간다. DB 조회는 Repository에
맡기고, 여기에는 그 결과로 판단하는 순수 로직만 둬 DB 없이 검증한다.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from news_weaver.domain.article import Article
from news_weaver.summarize.service import SummarizedGroup

# "같은 날"의 기준. 수신자가 한국에 있으므로 UTC 날짜를 쓰면 오전 9시를
# 경계로 날짜가 바뀌어, 아침 배치와 재실행이 다른 날로 취급될 수 있다
DELIVERY_TIMEZONE = timezone(timedelta(hours=9))


@dataclass(frozen=True, slots=True)
class DeliveryContents:
    """한 번의 발송에 실린 그룹과 기사의 식별자."""

    # 요약 캐시 키와 같은 값. 어떤 브리핑이 나갔는지 추적한다
    content_keys: tuple[str, ...]

    # 그룹에 속한 모든 기사. 다음 실행에서 제외할 기준이 된다
    url_hashes: tuple[str, ...]


def delivery_date_of(sent_at: datetime) -> date:
    """발송 시각을 한국 시간 기준 날짜로 바꾼다."""
    return sent_at.astimezone(DELIVERY_TIMEZONE).date()


def should_skip_delivery(already_delivered_today: bool, force: bool) -> bool:
    """
    오늘 이미 보냈다면 건너뛴다. 강제 실행이면 그대로 진행한다.

    강제 실행이어도 이미 보낸 기사는 exclude_delivered로 빠지므로,
    같은 내용이 다시 가지는 않는다.
    """
    return already_delivered_today and not force


def exclude_delivered(
    articles: list[Article],
    delivered_url_hashes: set[str],
) -> list[Article]:
    """
    이전에 보낸 기사를 후보에서 뺀다.

    그룹 키가 아니라 기사 단위로 거르는 이유는, 어제 보낸 사건에 오늘
    기사 하나가 더 붙으면 그룹 키가 달라져 같은 사건이 다시 나가기 때문이다.
    입력 순서는 유지한다.
    """
    return [
        article for article in articles if article.url_hash not in delivered_url_hashes
    ]


def collect_delivery_contents(summarized: list[SummarizedGroup]) -> DeliveryContents:
    """
    실제로 메일에 실린 그룹과 기사를 모은다.

    요약에 실패해 빠진 그룹은 포함하지 않는다. 기록하면 다음 실행에서
    제외되어 한 번도 전달되지 못한 채 사라진다.
    """
    content_keys = tuple(item.group.group_key for item in summarized)
    url_hashes = tuple(
        member.article.url_hash
        for item in summarized
        for member in item.group.members
    )

    return DeliveryContents(content_keys=content_keys, url_hashes=url_hashes)
