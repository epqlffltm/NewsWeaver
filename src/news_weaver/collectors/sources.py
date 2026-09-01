# NewsWeaver/src/news_weaver/collectors/sources.py

"""
수집 대상 RSS 소스 목록.

소스가 늘어나면 이 파일만 수정하면 되도록, 수집 로직과 대상 목록을 분리한다.
운영 중 소스를 추가·중단할 필요가 생기면 DB로 옮기게 되지만, 지금은
코드 상수로 두는 편이 단순하다.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RssSource:
    """RSS 수집 대상 소스 하나."""

    name: str
    url: str
    
RSS_SOURCES: tuple[RssSource, ...] = (
    RssSource("ZDNet", "https://feeds.feedburner.com/zdkorea"),
    RssSource("전자신문", "https://rss.etnews.com/Section901.xml"),
    RssSource("블로터", "https://www.bloter.net/rss/allArticle.xml"),
    RssSource("한겨레_경제", "https://www.hani.co.kr/rss/economy/"),
)