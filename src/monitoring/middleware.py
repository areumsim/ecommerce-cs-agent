"""모니터링 미들웨어.

FastAPI 미들웨어로 HTTP 요청을 자동 추적합니다.
"""

from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .metrics import track_request


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Prometheus 메트릭 수집 미들웨어.

    모든 HTTP 요청의 시간과 상태를 자동으로 기록합니다.
    """

    def __init__(self, app, exclude_paths: list[str] | None = None):
        """초기화.

        Args:
            app: FastAPI 앱
            exclude_paths: 제외할 경로 목록 (예: ["/metrics", "/healthz"])
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/metrics", "/healthz", "/health", "/ready"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 메트릭 기록."""
        path = request.url.path

        # 제외 경로 체크
        if path in self.exclude_paths:
            return await call_next(request)

        # 요청 시간 측정
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time

            # 엔드포인트 정규화 (경로 파라미터 제거)
            endpoint = self._normalize_path(path)

            # 메트릭 기록
            track_request(
                method=request.method,
                endpoint=endpoint,
                status=status_code,
                duration=duration,
            )

        return response

    def _normalize_path(self, path: str) -> str:
        """경로 정규화 (ID 등을 플레이스홀더로 대체).

        예: /orders/ORD-123 -> /orders/{order_id}
        """
        parts = path.split("/")
        normalized = []

        for i, part in enumerate(parts):
            if not part:
                continue

            # ID 패턴 감지 및 대체
            if part.startswith("ORD") or part.startswith("ord"):
                normalized.append("{order_id}")
            elif part.startswith("TKT") or part.startswith("tkt"):
                normalized.append("{ticket_id}")
            elif part.startswith("conv_"):
                normalized.append("{conversation_id}")
            elif part.startswith("user_"):
                normalized.append("{user_id}")
            elif part.startswith("msg_"):
                normalized.append("{message_id}")
            elif self._is_uuid_like(part):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/" + "/".join(normalized)

    def _is_uuid_like(self, s: str) -> bool:
        """UUID 형태 문자열 감지."""
        # 12자 이상의 영숫자 문자열 (UUID, 해시 등)
        if len(s) >= 12 and s.replace("-", "").replace("_", "").isalnum():
            # 순수 숫자는 제외
            if not s.isdigit():
                return True
        return False
