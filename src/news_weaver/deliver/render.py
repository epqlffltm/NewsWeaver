# NewsWeaver/src/news_weaver/deliver/render.py

"""
요약 결과를 메일 본문으로 변환한다.

발송 수단과 무관한 순수 변환이므로 분리한다. 링크를 눌러 원문으로 갈 수
있어야 하므로 HTML로 만들며, 원문 주소는 정규화하지 않은 값을 쓴다.

여러 매체가 같은 사건을 다룬 경우 출처를 모두 표시한다. 어느 매체가 다뤘는지가
사건의 비중을 보여주고, 종합 요약의 근거를 확인할 수 있게 하기 위함이다.
"""

from datetime import datetime
from html import escape

from news_weaver.summarize.service import SummarizedGroup

_SOURCE_LINK = '<a href="{url}">{source}</a>'

_ITEM_TEMPLATE = """<div style="margin-bottom:28px">
  <h3 style="margin:0 0 6px">{title}</h3>
  <div style="color:#888;font-size:13px;margin-bottom:6px">{published} · {sources}</div>
  <div style="line-height:1.6">{summary}</div>
</div>"""

_PAGE_TEMPLATE = """<div style="font-family:sans-serif;max-width:680px">
  <h2>{heading}</h2>
  {items}
  <hr>
  <div style="color:#aaa;font-size:12px">NewsWeaver</div>
</div>"""


def build_subject(sent_at: datetime, item_count: int) -> str:
    """메일 제목을 만든다."""
    return f"[NewsWeaver] {sent_at:%Y-%m-%d} 뉴스 다이제스트 {item_count}건"


def _format_published(item: SummarizedGroup) -> str:
    """발행 시각을 표시용 문자열로 만든다. 없는 소스는 수집 시각을 쓴다."""
    article = item.group.representative.article
    moment = article.published_at or article.collected_at

    return f"{moment:%Y-%m-%d %H:%M}"


def _render_sources(item: SummarizedGroup) -> str:
    """
    구성원의 출처를 링크 목록으로 만든다.

    묶인 기사가 여럿이면 모두 표시해, 종합 요약의 근거를 확인할 수 있게 한다.
    """
    return " · ".join(
        _SOURCE_LINK.format(
            # 정규화된 주소는 중복 판정용이므로 접속에는 원본을 쓴다
            url=escape(member.article.url, quote=True),
            source=escape(member.article.source_name),
        )
        for member in item.group.members
    )


def _render_item(item: SummarizedGroup) -> str:
    """그룹 하나를 HTML 조각으로 만든다."""
    representative = item.group.representative.article

    return _ITEM_TEMPLATE.format(
        # 제목과 요약에는 기사 원문이 들어가므로 반드시 이스케이프한다
        title=escape(representative.title),
        published=_format_published(item),
        sources=_render_sources(item),
        summary=escape(item.summary_text).replace("\n", "<br>"),
    )


def render_digest(items: list[SummarizedGroup], sent_at: datetime) -> str:
    """요약된 그룹들을 메일 본문 HTML로 만든다."""
    heading = f"{sent_at:%Y년 %m월 %d일} 뉴스 다이제스트"
    rendered = "\n".join(_render_item(item) for item in items)

    return _PAGE_TEMPLATE.format(heading=heading, items=rendered)