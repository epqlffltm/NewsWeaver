# NewsWeaver/tests/test_config.py

"""
설정 읽기가 잘못된 값을 배치 시작 시점에 걸러내는지 검증한다.
"""

import pytest

from news_weaver.config import get_database_url, get_settings
from news_weaver.db.tables import EMBEDDING_DIMENSION

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/db",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "gemma",
    "EMBEDDING_MODEL": "embeddinggemma",
    "EMBEDDING_DIMENSION": str(EMBEDDING_DIMENSION),
    "DUPLICATE_SIMILARITY_THRESHOLD": "0.6",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "user",
    "SMTP_PASSWORD": "secret",
    "MAIL_RECIPIENT": "me@example.com",
}


@pytest.fixture
def full_env(monkeypatch):
    """모든 필수 환경변수를 채우고, 캐시된 설정을 비운다."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_settings_load_when_dimension_matches_schema(full_env) -> None:
    """차원이 스키마와 같으면 정상적으로 읽힌다."""
    settings = get_settings()

    assert settings.embedding_dimension == EMBEDDING_DIMENSION


def test_dimension_mismatch_fails_fast(full_env) -> None:
    """
    차원이 스키마와 다르면 시작 시점에 실패한다.

    그대로 두면 수집을 마친 뒤 임베딩 저장에서야 DB 오류가 나기 때문이다.
    """
    full_env.setenv("EMBEDDING_DIMENSION", str(EMBEDDING_DIMENSION + 1))

    with pytest.raises(RuntimeError, match="EMBEDDING_DIMENSION"):
        get_settings()


def test_database_url_does_not_require_other_settings(monkeypatch) -> None:
    """
    DB 주소만 읽을 때는 SMTP·Ollama 설정이 없어도 된다.

    마이그레이션이 DB 외 설정에 묶이지 않게 하기 위함이다.
    """
    for key in REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")

    assert get_database_url() == "postgresql+psycopg://u:p@localhost/db"
