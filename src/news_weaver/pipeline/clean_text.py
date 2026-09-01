# NewsWeaver/src/news_weaver/pipeline/clean_text.py

"""
피드가 제공하는 텍스트에서 마크업과 잡음을 제거한다.

소스에 따라 요약 필드에 기사 내용 대신 썸네일용 HTML이 들어 있는 경우가
있어, 그대로 두면 요약·임베딩 품질이 떨어진다. 정제 후 내용이 남지 않으면
요약이 없는 것으로 간주한다.
"""

import html
import re

# HTML 태그 한 개를 통째로 찾는다. 예: <table border="0">, </td>
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# 연속된 공백·줄바꿈을 하나로 합치기 위한 패턴
WHITESPACE_PATTERN = re.compile(r"\s+")

# 정제 후 이 길이 미만이면 의미 있는 요약이 아니라고 본다
MINIMUM_MEANINGFUL_LENGTH = 20

def strip_html(raw_text: str) -> str:
    """
    HTML 태그를 제거하고 엔티티를 문자로 되돌린 뒤 공백을 정리한다.
    """
    without_tags = HTML_TAG_PATTERN.sub(" ", raw_text)
    unescaped = html.unescape(without_tags)
    return WHITESPACE_PATTERN.sub(" ", unescaped).strip()

def clean_summary(raw_summary: str | None) -> str | None:
    """
    요약 필드를 정제한다. 의미 있는 내용이 남지 않으면 None을 반환한다.
    """
    
    if not raw_summary:
        return None
    
    cleaned = strip_html(raw_summary)
    
    if len(cleaned) < MINIMUM_MEANINGFUL_LENGTH:
        return None
    
    return cleaned