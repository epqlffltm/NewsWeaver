# NewsWeaver/tests/test_normalize.py

"""
URL 정규화 규칙이 의도대로 동작하는지 검증한다.
"""

import pytest

from news_weaver.pipeline.normalize import hash_url, normalize_url


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        # 스킴 통일
        ("http://zdnet.co.kr/view", "https://zdnet.co.kr/view"),

        # 호스트 소문자
        ("https://ZDNet.co.kr/view", "https://zdnet.co.kr/view"),

        # 끝 슬래시 제거
        ("https://test.com/path/", "https://test.com/path"),

        # 프래그먼트 제거
        ("https://test.com/path#comment", "https://test.com/path"),

        # 추적 파라미터 제거
        ("https://test.com/path?utm_source=twitter&fbclid=123", "https://test.com/path"),

        # 쿼리 정렬
        ("https://test.com/path?b=2&a=1", "https://test.com/path?a=1&b=2"),

        # 식별에 필요한 쿼리는 유지된다
        ("https://zdnet.co.kr/view/?no=20260901082807",
         "https://zdnet.co.kr/view?no=20260901082807"),
    ],
)
def test_normalize_url(raw_url: str, expected: str) -> None:
    assert normalize_url(raw_url) == expected


def test_url_variants_share_same_hash() -> None:
    """
    같은 기사의 URL 변형들은 하나의 해시로 모인다.
    """
    variants = [
        "https://zdnet.co.kr/view/?no=123",
        "http://ZDNet.co.kr/view?no=123",
        "https://zdnet.co.kr/view/?no=123&utm_source=naver",
        "https://zdnet.co.kr/view/?no=123#comment",
    ]
    hashes = {hash_url(normalize_url(url)) for url in variants}
    assert len(hashes) == 1


def test_different_articles_have_different_hashes() -> None:
    """
    서로 다른 기사는 다른 해시를 가진다.
    """
    first = hash_url(normalize_url("https://zdnet.co.kr/view/?no=123"))
    second = hash_url(normalize_url("https://zdnet.co.kr/view/?no=456"))
    assert first != second