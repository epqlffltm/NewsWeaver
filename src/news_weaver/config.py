# NewsWeaver/src/news_weaver/config.py

"""
환경변수를 읽어 설정 객체로 제공한다.

여러 모듈이 os.environ을 직접 참조하면 어떤 설정이 필요한지 흩어져
파악하기 어려워지므로, 읽기와 검증을 이 모듈 한 곳에 모은다.
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Settings:
    """애플리케이션 실행에 필요한 설정값."""

    database_url: str


def _require_env(key: str) -> str:
    """필수 환경변수를 읽는다. 없으면 즉시 실패시킨다."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"환경변수 {key}가 설정되지 않았습니다. .env 파일을 확인하세요."
        )
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """설정을 한 번만 읽어 재사용한다."""
    return Settings(database_url=_require_env("DATABASE_URL"))