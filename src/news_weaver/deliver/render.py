# NewsWeaver/src/news_weaver/deliver/render.py

"""
요약 결과를 메일 본문으로 변환한다.

발송 수단과 무관한 순수 변환이므로 분리한다. 링크를 눌러 원문으로 갈 수
있어야 하므로 HTML로 만들며, 원문 주소는 정규화하지 않은 값을 쓴다.
"""

from datetime import datetime
from html import escape

from news_weaver.summarize.service import SummarizedArticle

_ARTICLE_TEMPLATE = """<div style="margin-bottom:28px">
  <h3 style="margin:0 0 6px"><a href="{url}">{title}</a></h3>
  <div style="color:#888;font-size:13px;margin-bottom:6px">{source} · {published}</div>
  <div style="line-height:1.6">{summary}</div>
</div>"""

_PAGE_TEMPLATE = """<div style="font-family:sans-serif;max-width:680px">
  <h2>{heading}</h2>
  {articles}
  <hr>
  <div style="color:#aaa;font-size:12px">NewsWeaver</div>
</div>"""


def build_subject(sent_at: datetime, article_count: int) -> str:
    """메일 제목을 만든다."""
    return f"[NewsWeaver] {sent_at:%Y-%m-%d} 뉴스 다이제스트 {article_count}건"


def _format_published(item: SummarizedArticle) -> str:
    """발행 시각을 표시용 문자열로 만든다. 없는 소스는 수집 시각을 쓴다."""
    moment = item.article.published_at or item.article.collected_at
    return f"{moment:%Y-%m-%d %H:%M}"


def _render_article(item: SummarizedArticle) -> str:
    """기사 한 건을 HTML 조각으로 만든다."""
    return _ARTICLE_TEMPLATE.format(
        # 제목과 요약에는 기사 원문이 들어가므로 반드시 이스케이프한다
        url=escape(item.article.url, quote=True),
        title=escape(item.article.title),
        source=escape(item.article.source_name),
        published=_format_published(item),
        summary=escape(item.summary_text).replace("\n", "<br>"),
    )


def render_digest(items: list[SummarizedArticle], sent_at: datetime) -> str:
    """요약된 기사들을 메일 본문 HTML로 만든다."""
    heading = f"{sent_at:%Y년 %m월 %d일} 뉴스 다이제스트"
    articles = "\n".join(_render_article(item) for item in items)

    return _PAGE_TEMPLATE.format(heading=heading, articles=articles)