# src/news_weaver/pipeline/normalize.py

"""
URL을 비교 가능한 형태로 정규화한다.

같은 기사가 스킴·대소문자·추적 파라미터 차이로 서로 다른 URL로
들어오는 것을 막아, 중복 판정의 기준을 만드는 것이 목적이다.
정규화된 URL은 비교에만 쓰며, 실제 접속에는 원본 URL을 사용한다.
"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAM_NAMES = frozenset({"fbclid", "gclid", "igshid"})


def _remove_tracking_params(query: str) -> str:
    """콘텐츠 식별과 무관한 추적 파라미터를 제거하고 순서를 정렬한다."""
    query_params = parse_qsl(query, keep_blank_values=True)
    return urlencode(sorted(
        (key, value)
        for key, value in query_params
        if not key.startswith(TRACKING_PARAM_PREFIXES)
        and key not in TRACKING_PARAM_NAMES
    ))


def _normalize_path(path: str) -> str:
    """경로 끝의 슬래시를 제거한다. 루트 경로는 그대로 둔다."""
    if path == "/":
        return path
    return path.rstrip("/")


def normalize_url(url: str) -> str:
    """URL을 중복 판정에 쓸 수 있는 표준 형태로 변환한다.

    접속이 아니라 비교에만 쓰이므로, 프로토콜 차이나 쿼리 순서처럼
    같은 리소스를 가리키는 변형은 모두 하나의 형태로 모은다.
    """
    parsed = urlsplit(url)

    return urlunsplit((
        "https",
        parsed.netloc.lower(),
        _normalize_path(parsed.path),
        _remove_tracking_params(parsed.query),
        "",
    ))
    
def hash_url(normalized_url: str) -> str:
    """정규화된 URL의 해시를 반환한다. DB 유니크 제약의 키로 쓴다."""
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()