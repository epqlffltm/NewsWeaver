# NewsWeaver/src/news_weaver/config.py

"""
환경변수를 읽어 설정 객체로 제공한다.

여러 모듈이 os.environ을 직접 참조하면 어떤 설정이 필요한지 흩어져
파악하기 어려워지므로, 읽기와 검증을 이 모듈 한 곳에 모은다.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from news_weaver.db.tables import EMBEDDING_DIMENSION


@dataclass(frozen=True, slots=True)
class Settings:
    """애플리케이션 실행에 필요한 설정값."""
    
    # 이 값 이상이면 같은 사건으로 본다. 모델마다 유사도 분포가 다르므로
    # 코드에 고정하지 않고 조정 가능하게 둔다
    duplicate_similarity_threshold: float

    database_url: str

    # 요약 모델과 서버 주소는 실행 환경의 성능에 따라 달라지므로 분리한다
    ollama_base_url: str
    ollama_model: str

    # 임베딩 차원은 벡터 컬럼 타입으로 스키마에 고정되므로, 설정과 스키마가
    # 어긋나면 임베딩 저장 단계에서야 실패한다. get_settings에서 미리 검증한다
    embedding_model: str
    embedding_dimension: int

    # 발송 계정 정보. 비밀번호가 포함되므로 저장소에 두지 않는다
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    mail_recipient: str


def _require_env(key: str) -> str:
    """필수 환경변수를 읽는다. 없으면 즉시 실패시킨다."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"환경변수 {key}가 설정되지 않았습니다. .env 파일을 확인하세요."
        )
    return value


def get_database_url() -> str:
    """
    DB 접속 주소만 읽는다.

    마이그레이션처럼 DB만 필요한 작업이 SMTP·Ollama 설정까지 요구하면
    CI나 새 환경에서 불필요한 값을 채워야 하므로, 전체 설정과 분리해 둔다.
    """
    return _require_env("DATABASE_URL")


def _validate_embedding_dimension(configured: int) -> None:
    """
    설정한 임베딩 차원이 스키마의 벡터 컬럼 차원과 같은지 확인한다.

    어긋나면 수집·요약이 다 끝난 뒤 임베딩 저장에서 DB 오류로 멈추므로,
    배치 시작 시점에 원인을 알 수 있는 메시지로 바로 실패시킨다.
    """
    if configured != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"EMBEDDING_DIMENSION={configured}이 스키마의 벡터 차원 "
            f"{EMBEDDING_DIMENSION}과 다릅니다. 모델을 바꿨다면 "
            "db/tables.py와 마이그레이션을 함께 수정하세요."
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """설정을 한 번만 읽어 재사용한다. 잘못된 설정은 여기서 바로 실패시킨다."""
    embedding_dimension = int(_require_env("EMBEDDING_DIMENSION"))
    _validate_embedding_dimension(embedding_dimension)

    return Settings(
        database_url=get_database_url(),
        ollama_base_url=_require_env("OLLAMA_BASE_URL"),
        ollama_model=_require_env("OLLAMA_MODEL"),
        embedding_model=_require_env("EMBEDDING_MODEL"),
        embedding_dimension=embedding_dimension,
        smtp_host=_require_env("SMTP_HOST"),
        smtp_port=int(_require_env("SMTP_PORT")),
        smtp_username=_require_env("SMTP_USERNAME"),
        smtp_password=_require_env("SMTP_PASSWORD"),
        mail_recipient=_require_env("MAIL_RECIPIENT"),
        duplicate_similarity_threshold=float(
            _require_env("DUPLICATE_SIMILARITY_THRESHOLD")
        ),
    )