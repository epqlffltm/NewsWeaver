# NewsWeaver/src/news_weaver/db/engine.py

"""
데이터베이스 연결을 생성하고 재사용한다.

엔진은 커넥션 풀을 들고 있어 매번 만들면 연결이 누적되므로,
프로세스 전체에서 하나만 유지한다.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from news_weaver.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """커넥션 풀을 가진 엔진을 한 번만 생성해 재사용한다."""
    return create_engine(get_settings().database_url, future=True)

@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """세션을 만들어내는 팩토리를 반환한다."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)