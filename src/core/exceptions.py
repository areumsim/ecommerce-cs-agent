"""커스텀 예외 클래스 모듈.

애플리케이션 전역에서 사용되는 예외 클래스를 정의합니다.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    """애플리케이션 기본 예외.

    모든 커스텀 예외의 기반 클래스입니다.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "내부 서버 오류가 발생했습니다"

    def __init__(
        self,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message or self.message
        self.error_code = error_code or self.error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """예외 정보를 딕셔너리로 반환."""
        result = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class AuthError(AppError):
    """인증 관련 예외."""

    status_code = 401
    error_code = "AUTH_ERROR"
    message = "인증에 실패했습니다"


class RateLimitError(AppError):
    """Rate Limit 초과 예외."""

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "요청 횟수가 제한을 초과했습니다"

    def __init__(
        self,
        message: Optional[str] = None,
        retry_after: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ValidationError(AppError):
    """입력 검증 실패 예외."""

    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "입력값이 유효하지 않습니다"


class NotFoundError(AppError):
    """리소스를 찾을 수 없음 예외."""

    status_code = 404
    error_code = "NOT_FOUND"
    message = "요청한 리소스를 찾을 수 없습니다"


class PermissionError(AppError):
    """권한 부족 예외."""

    status_code = 403
    error_code = "PERMISSION_DENIED"
    message = "이 작업을 수행할 권한이 없습니다"


class ConflictError(AppError):
    """리소스 충돌 예외."""

    status_code = 409
    error_code = "CONFLICT"
    message = "리소스 충돌이 발생했습니다"


class ServiceUnavailableError(AppError):
    """서비스 이용 불가 예외."""

    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
    message = "서비스를 일시적으로 사용할 수 없습니다"
