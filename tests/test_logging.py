"""로깅 모듈 테스트."""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from src.core.logging import (
    ContextLogger,
    JSONFormatter,
    get_logger,
    get_request_id,
    get_user_id,
    log_debug,
    log_error,
    log_info,
    log_warning,
    request_id_var,
    set_request_id,
    set_user_id,
    setup_logging,
    user_id_var,
)


class TestRequestIdContext:
    """요청 ID 컨텍스트 테스트."""

    def setup_method(self):
        """각 테스트 전 컨텍스트 초기화."""
        request_id_var.set(None)
        user_id_var.set(None)

    def test_get_request_id_default_none(self):
        """기본값은 None."""
        assert get_request_id() is None

    def test_set_request_id_custom(self):
        """커스텀 요청 ID 설정."""
        result = set_request_id("test-req-123")
        assert result == "test-req-123"
        assert get_request_id() == "test-req-123"

    def test_set_request_id_auto_generate(self):
        """자동 생성 요청 ID."""
        result = set_request_id()
        assert result is not None
        assert len(result) == 8  # uuid[:8]
        assert get_request_id() == result

    def test_get_user_id_default_none(self):
        """기본값은 None."""
        assert get_user_id() is None

    def test_set_user_id(self):
        """사용자 ID 설정."""
        set_user_id("user_001")
        assert get_user_id() == "user_001"

    def test_set_user_id_none(self):
        """사용자 ID None 설정."""
        set_user_id("user_001")
        set_user_id(None)
        assert get_user_id() is None


class TestJSONFormatter:
    """JSON 포매터 테스트."""

    def setup_method(self):
        """각 테스트 전 컨텍스트 초기화."""
        request_id_var.set(None)
        user_id_var.set(None)

    def test_format_basic_log(self):
        """기본 로그 포맷."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=10,
            msg="테스트 메시지",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "테스트 메시지"
        assert "timestamp" in data
        assert data["source"]["line"] == 10

    def test_format_with_request_id(self):
        """요청 ID 포함."""
        set_request_id("req-456")
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=10,
            msg="테스트",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert data["request_id"] == "req-456"

    def test_format_with_user_id(self):
        """사용자 ID 포함."""
        set_user_id("user_789")
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=10,
            msg="테스트",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert data["user_id"] == "user_789"

    def test_format_with_exception(self):
        """예외 정보 포함."""
        formatter = JSONFormatter()
        try:
            raise ValueError("테스트 예외")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/test.py",
            lineno=10,
            msg="에러 발생",
            args=(),
            exc_info=exc_info,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_format_with_extra_fields(self):
        """추가 필드 포함."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=10,
            msg="테스트",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"custom_key": "custom_value"}
        result = formatter.format(record)
        data = json.loads(result)

        assert data["custom_key"] == "custom_value"


class TestContextLogger:
    """컨텍스트 로거 테스트."""

    def setup_method(self):
        """각 테스트 전 컨텍스트 초기화."""
        request_id_var.set(None)
        user_id_var.set(None)

    def test_process_adds_request_id(self):
        """요청 ID 추가."""
        set_request_id("ctx-123")
        logger = logging.getLogger("test")
        ctx_logger = ContextLogger(logger, {})

        msg, kwargs = ctx_logger.process("테스트", {})
        assert kwargs["extra"]["request_id"] == "ctx-123"

    def test_process_adds_user_id(self):
        """사용자 ID 추가."""
        set_user_id("user_ctx")
        logger = logging.getLogger("test")
        ctx_logger = ContextLogger(logger, {})

        msg, kwargs = ctx_logger.process("테스트", {})
        assert kwargs["extra"]["user_id"] == "user_ctx"

    def test_process_preserves_existing_extra(self):
        """기존 extra 보존."""
        logger = logging.getLogger("test")
        ctx_logger = ContextLogger(logger, {})

        msg, kwargs = ctx_logger.process("테스트", {"extra": {"existing": "value"}})
        assert kwargs["extra"]["existing"] == "value"


class TestSetupLogging:
    """로깅 설정 테스트."""

    def test_setup_console_only(self):
        """콘솔만 설정."""
        logger = setup_logging(level="DEBUG", json_format=True)
        assert logger.level == logging.DEBUG
        # 핸들러가 있는지 확인
        assert len(logger.handlers) >= 1

    def test_setup_with_file(self):
        """파일 핸들러 포함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(level="INFO", log_file=str(log_file))

            # 파일 핸들러 추가됨
            file_handlers = [
                h for h in logger.handlers
                if hasattr(h, "baseFilename")
            ]
            assert len(file_handlers) >= 1

    def test_setup_standard_format(self):
        """표준 포맷."""
        logger = setup_logging(level="INFO", json_format=False)
        assert logger.level == logging.INFO


class TestGetLogger:
    """get_logger 테스트."""

    def test_get_logger_returns_context_logger(self):
        """ContextLogger 반환."""
        logger = get_logger("test_module")
        assert isinstance(logger, ContextLogger)


class TestConvenienceFunctions:
    """편의 함수 테스트."""

    def test_log_info(self, caplog):
        """INFO 로그."""
        with caplog.at_level(logging.INFO):
            log_info("정보 메시지", key="value")

    def test_log_warning(self, caplog):
        """WARNING 로그."""
        with caplog.at_level(logging.WARNING):
            log_warning("경고 메시지")

    def test_log_error(self, caplog):
        """ERROR 로그."""
        with caplog.at_level(logging.ERROR):
            log_error("에러 메시지")

    def test_log_debug(self, caplog):
        """DEBUG 로그."""
        with caplog.at_level(logging.DEBUG):
            log_debug("디버그 메시지")
