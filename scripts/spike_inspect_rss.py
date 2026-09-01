# scripts/spike_inspect_rss.py

"""
RSS 피드의 실제 구조를 확인하기위해 사용하는 일회성 스크립트

스키마와 도메인 모델을 설계하기 전에, 실제 피드가 어떤 필드를 제공하고
어떤 값이 비어 있거나 형식이 제각각인지 눈으로 확인하는 것이 목적
"""

import feedparser

FEED_URLS = {
    "연합뉴스": "https://www.yna.co.kr/rss/all.xml",
    "한겨레_경제": "https://www.hani.co.kr/rss/economy/",
    "ZDNet_코리아": "https://feeds.feedburner.com/zdkorea",
}

INSPECTED_FIELDS = ("title", "link", "published", "updated" , "author", "summary")

def print_entry_fields(entry)->None:
    """항목 하나가 어떤 필드를 갖고 각 값이 어떤 모습인지 출력한다."""
    print(f"\n  보유 필드: {sorted(entry.keys())}")
    
    for field_name in INSPECTED_FIELDS:
        raw_value = entry.get(field_name)
        if raw_value is None:
            print(f"  {field_name:10}: (없음)")
        else:
            print(f"  {field_name:10}: {str(raw_value)[:130]}")

    print(f"  {'parsed':10}: {entry.get('published_parsed')}")


def inspect_feed(source_name: str, feed_url: str, sample_size: int = 2) -> None:
    """피드를 파싱해 상위 몇 건의 구조를 출력한다."""
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