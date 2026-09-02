# NewsWeaver/src/news_weaver/logging_config.py

"""
로그 출력 방식을 진입점에서 한 번만 설정한다.

라이브러리 코드는 무슨 일이 있었는지 기록만 하고, 그 기록을 어디로 보낼지는
실행 주체가 정한다. 그래야 같은 코드가 CLI에서는 콘솔과 파일로, 웹에서는
다른 방식으로 나갈 수 있다.

배치는 사람이 보지 않는 시각에 실행되므로 파일 기록이 없으면 실패를
사후에 추적할 수 없다.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIRECTORY = Path("logs")
LOG_FILE_NAME = "newsweaver.log"

# 로그가 무한히 쌓이면 디스크를 채우므로 크기로 순환시킨다
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

_CONSOLE_FORMAT = "%(message)s"
_FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"


def _build_console_handler() -> logging.Handler:
    """사람이 지켜볼 때 읽기 좋도록 간결하게 출력한다."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    handler.setLevel(logging.INFO)
    return handler


def _build_file_handler() -> logging.Handler:
    """
    사후 추적을 위해 시각과 출처를 포함해 파일에 남긴다.

    Windows와 Linux에서 동작이 갈리지 않도록 인코딩을 명시한다.
    """
    LOG_DIRECTORY.mkdir(exist_ok=True)

    handler = RotatingFileHandler(
        LOG_DIRECTORY / LOG_FILE_NAME,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    handler.setLevel(logging.DEBUG)
    return handler


def configure_logging() -> None:
    """
    콘솔과 파일 양쪽으로 로그를 보내도록 설정한다.

    진입점에서 한 번만 호출한다. 여러 번 호출하면 핸들러가 중복 등록되어
    같은 줄이 여러 번 출력되므로 기존 핸들러를 먼저 비운다.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    root_logger.addHandler(_build_console_handler())
    root_logger.addHandler(_build_file_handler())

    # 외부 라이브러리의 상세 로그는 우리 기록을 덮으므로 낮춘다
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)