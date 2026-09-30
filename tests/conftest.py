# NewsWeaver/tests/conftest.py

"""
테스트 공용 픽스처.

통합 테스트는 실제 PostgreSQL이 있어야 하므로, DATABASE_URL이 없는 로컬
환경에서는 건너뛰어 `pytest`만으로도 단위 테스트가 돌게 한다.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# 테스트 모듈이 news_weaver.cli를 임포트하면 load_dotenv()가 .env를 읽어
# 개발용 DB 주소가 환경에 들어온다. 그 전에 읽어 두어, 명시적으로 지정한
# 경우에만 통합 테스트가 실행되게 한다
INTEGRATION_DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest.fixture
def db_session():
    """
    테스트마다 트랜잭션을 열고 끝나면 되돌리는 세션.

    테스트끼리 데이터가 섞이지 않고, 실수로 개발 DB를 가리켜도 흔적이
    남지 않게 하기 위함이다. 스키마는 `alembic upgrade head`로 미리 만든다.
    """
    if not INTEGRATION_DATABASE_URL:
        pytest.skip("DATABASE_URL이 없어 통합 테스트를 건너뜁니다.")

    engine = create_engine(INTEGRATION_DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
