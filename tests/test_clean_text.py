# NewsWeaver/tests/test_clean_text.py

"""
텍스트 정제가 마크업과 무의미한 요약을 걸러내는지 검증한다.
"""

from news_weaver.pipeline.clean_text import clean_summary, strip_html


def test_strip_html_removes_tags() -> None:
    """
    태그를 제거하고 텍스트만 남긴다.
    """
    assert strip_html("<p>안녕하세요</p>") == "안녕하세요"


def test_strip_html_keeps_word_boundary() -> None:
    """
    태그를 지우면서 단어가 붙지 않도록 공백을 유지한다.
    """
    assert strip_html("<p>가나</p><p>다라</p>") == "가나 다라"


def test_strip_html_unescapes_entities() -> None:
    """
    HTML 엔티티를 원래 문자로 되돌린다.
    """
    assert strip_html("A&amp;B") == "A&B"


def test_clean_summary_returns_none_for_markup_only() -> None:
    """
    썸네일용 테이블만 든 요약은 내용이 없으므로 None이 된다.
    """
    thumbnail_markup = '<table border="0px"><tr><td bgcolor="#DDDDDD"></td></tr></table>'

    assert clean_summary(thumbnail_markup) is None


def test_clean_summary_keeps_real_text() -> None:
    """
    실제 기사 요약은 정제 후에도 유지된다.
    """
    raw = "집에서 고효율 필터가 장착된 공기청정기를 한 달간 사용한 성인의 인지검사 결과가 나왔다."

    assert clean_summary(raw) == raw


def test_clean_summary_handles_missing_value() -> None:
    """
    요약을 제공하지 않는 소스는 None을 반환한다.
    """
    assert clean_summary(None) is None