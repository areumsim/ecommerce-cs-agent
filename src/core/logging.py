"""JSON 구조화 로깅 모듈.

structlog 기반 JSON 포맷 로깅을 제공합니다.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

# 요청 ID 컨텍스트
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def get_request_id() -> Optional[str]:
    """현재 요청 ID 반환."""
    return request_id_var.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """요청 ID 설정."""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    request_id_var.set(request_id)
    return request_id


def get_user_id() -> Optional[str]:
    """현재 사용자 ID 반환."""
    return user_id_var.get()


def set_user_id(user_id: Optional[str]) -> None:
    """사용자 ID 설정."""
    user_id_var.set(user_id)


class JSONFormatter(logging.Formatter):
    """JSON 포맷 로그 포매터."""

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 JSON 문자열로 포맷."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 요청 컨텍스트 추가
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        user_id = get_user_id()
        if user_id:
            log_data["user_id"] = user_id

        # 추가 필드
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # 예외 정보
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 소스 위치
        log_data["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ContextLogger(logging.LoggerAdapter):
    """컨텍스트 정보를 포함하는 로거 어댑터."""

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """로그 메시지 처리."""
        extra = kwargs.get("extra", {})

        # 컨텍스트 정보 추가
        request_id = get_request_id()
        if request_id:
            extra["request_id"] = request_id

        user_id = get_user_id()
        if user_id:
            extra["user_id"] = user_id

        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    json_format: bool = True,
) -> logging.Logger:
    """로깅 설정.

    Args:
        level: 로그 레벨
        log_file: 로그 파일 경로 (None이면 콘솔만)
        max_bytes: 로그 파일 최대 크기
        backup_count: 백업 파일 수
        json_format: JSON 포맷 사용 여부

    Returns:
        설정된 루트 로거
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 포매터 선택
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (로테이션)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> ContextLogger:
    """컨텍스트 로거 반환.

    Args:
        name: 로거 이름

    Returns:
        ContextLogger 인스턴스
    """
    logger = logging.getLogger(name)
    return ContextLogger(logger, {})


# 편의 함수
def log_info(message: str, **kwargs) -> None:
    """INFO 레벨 로그."""
    logger = get_logger("app")
    logger.info(message, extra={"extra_fields": kwargs})


def log_warning(message: str, **kwargs) -> None:
    """WARNING 레벨 로그."""
    logger = get_logger("app")
    logger.warning(message, extra={"extra_fields": kwargs})


def log_error(message: str, **kwargs) -> None:
    """ERROR 레벨 로그."""
    logger = get_logger("app")
    logger.error(message, extra={"extra_fields": kwargs})


def log_debug(message: str, **kwargs) -> None:
    """DEBUG 레벨 로그."""
    logger = get_logger("app")
    logger.debug(message, extra={"extra_fields": kwargs})
