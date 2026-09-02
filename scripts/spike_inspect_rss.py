# NewsWeaver/scripts/spike_inspect_rss.py

"""
RSS 피드의 실제 구조를 확인하기 위한 일회성 스파이크 스크립트.

스키마와 도메인 모델을 설계하기 전에, 실제 피드가 어떤 필드를 제공하고
어떤 값이 비어 있거나 형식이 제각각인지 눈으로 확인하는 것이 목적이다.
확인이 끝나면 삭제하며, 프로덕션 코드에서 임포트하지 않는다.
"""

import feedparser

FEED_URLS = {
    "디지털데일리": "https://www.ddaily.co.kr/rss/allArticle.xml",
    "IT조선": "https://it.chosun.com/rss/allArticle.xml",
    "아이뉴스24_IT": "https://www.inews24.com/rss/it_all.xml",
    "테크M": "https://www.techm.kr/rss/allArticle.xml",
}
INSPECTED_FIELDS = ("title", "link", "published", "updated", "author", "summary")


def summarize_field_health(entry) -> str:
    """
    항목이 실제로 쓸 만한 필드를 갖췄는지 한 줄로 요약한다.
    """
    has_parsed_date = entry.get("published_parsed") is not None
    raw_summary = str(entry.get("summary", ""))
    looks_like_html = raw_summary.strip().startswith("<")

    return (
        f"날짜={'O' if has_parsed_date else 'X'} "
        f"작성자={'O' if entry.get('author') else 'X'} "
        f"요약={'HTML덩어리' if looks_like_html else 'O'}"
    )


def print_entry_fields(entry) -> None:
    """
    항목 하나가 어떤 필드를 갖고 각 값이 어떤 모습인지 출력한다.
    """
    print(f"\n  보유 필드: {sorted(entry.keys())}")

    for field_name in INSPECTED_FIELDS:
        raw_value = entry.get(field_name)
        if raw_value is None:
            print(f"  {field_name:10}: (없음)")
        else:
            print(f"  {field_name:10}: {str(raw_value)[:130]}")

    print(f"  {'parsed':10}: {entry.get('published_parsed')}")
    print(f"  {'상태':10}: {summarize_field_health(entry)}")


def inspect_feed(source_name: str, feed_url: str, sample_size: int = 2) -> None:
    """
    피드를 파싱해 상위 몇 건의 구조를 출력한다.
    """
    parsed_feed = feedparser.parse(feed_url)

    print(f"\n{'=' * 70}")
    print(f"[{source_name}] 수집 {len(parsed_feed.entries)}건 / bozo={parsed_feed.bozo}")

    if parsed_feed.bozo:
        print(f"  파싱 경고: {parsed_feed.get('bozo_exception')}")

    for entry in parsed_feed.entries[:sample_size]:
        print_entry_fields(entry)


def main() -> None:
    for source_name, feed_url in FEED_URLS.items():
        inspect_feed(source_name, feed_url)


if __name__ == "__main__":
    main()