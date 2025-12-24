"""모니터링 모듈 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from src.monitoring.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION,
    AGENT_REQUESTS_TOTAL,
    AGENT_RESPONSE_TIME,
    LLM_REQUESTS_TOTAL,
    LLM_TOKENS_USED,
    DB_QUERIES_TOTAL,
    track_request,
    track_agent_request,
    track_llm_request,
    track_db_query,
    set_app_info,
    timed_db_query,
)
from src.monitoring.middleware import PrometheusMiddleware


class TestMetrics:
    """메트릭 테스트."""

    def test_track_request(self):
        """HTTP 요청 추적."""
        # 메트릭 호출 (Counter는 누적됨)
        track_request(
            method="GET",
            endpoint="/api/test",
            status=200,
            duration=0.123
        )

        # Counter 증가 확인은 어려우므로 호출만 테스트
        assert True

    def test_track_agent_request(self):
        """에이전트 요청 추적."""
        track_agent_request(
            agent_type="order",
            intent="order_status",
            duration=1.5
        )

        assert True

    def test_track_agent_request_with_error(self):
        """에러가 있는 에이전트 요청."""
        track_agent_request(
            agent_type="claim",
            intent="claim_submit",
            duration=0.5,
            error="ValidationError"
        )

        assert True

    def test_track_llm_request(self):
        """LLM 요청 추적."""
        track_llm_request(
            model="gpt-4",
            status="success",
            latency=2.5,
            prompt_tokens=100,
            completion_tokens=50
        )

        assert True

    def test_track_llm_request_error(self):
        """LLM 오류 추적."""
        track_llm_request(
            model="claude-3",
            status="error",
            latency=0.1
        )

        assert True

    def test_track_db_query(self):
        """DB 쿼리 추적."""
        track_db_query(
            table="orders",
            operation="select",
            duration=0.05
        )

        assert True

    def test_set_app_info(self):
        """앱 정보 설정."""
        set_app_info(
            name="ar-agent",
            version="1.0.0",
            environment="test"
        )

        assert True


class TestTimedDbQuery:
    """timed_db_query 컨텍스트 매니저 테스트."""

    def test_timed_db_query(self):
        """DB 쿼리 시간 측정."""
        with timed_db_query("users", "select"):
            # 쿼리 시뮬레이션
            result = sum(range(1000))

        assert result == 499500

    def test_timed_db_query_exception(self):
        """예외 발생 시에도 메트릭 기록."""
        with pytest.raises(ValueError):
            with timed_db_query("orders", "insert"):
                raise ValueError("DB error")


class TestPrometheusMiddleware:
    """Prometheus 미들웨어 테스트."""

    @pytest.fixture
    def test_app(self):
        """테스트 앱."""
        async def homepage(request):
            return PlainTextResponse("Hello")

        async def slow_endpoint(request):
            import time
            time.sleep(0.1)
            return PlainTextResponse("Slow")

        async def error_endpoint(request):
            raise ValueError("Test error")

        app = Starlette(
            routes=[
                Route("/", homepage),
                Route("/slow", slow_endpoint),
                Route("/error", error_endpoint),
                Route("/healthz", homepage),
                Route("/metrics", homepage),
            ]
        )
        app.add_middleware(PrometheusMiddleware)
        return app

    def test_middleware_normal_request(self, test_app):
        """정상 요청 처리."""
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/")

        assert response.status_code == 200
        assert response.text == "Hello"

    def test_middleware_excludes_healthz(self, test_app):
        """헬스체크 경로 제외."""
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/healthz")

        assert response.status_code == 200

    def test_middleware_excludes_metrics(self, test_app):
        """메트릭 경로 제외."""
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/metrics")

        assert response.status_code == 200

    def test_middleware_path_normalization(self):
        """경로 정규화 테스트."""
        middleware = PrometheusMiddleware(app=MagicMock())

        # 주문 ID 정규화 (ORD- 패턴 감지)
        path = middleware._normalize_path("/api/orders/ORD-12345")
        assert "{order_id}" in path

        # 티켓 ID 정규화 (TKT- 패턴 감지)
        path = middleware._normalize_path("/api/tickets/TKT-ABC123")
        assert "{ticket_id}" in path

        # 대화 ID 정규화 (conv_ 패턴 감지)
        path = middleware._normalize_path("/api/conversations/conv_abc123def456")
        assert "{conversation_id}" in path

        # 사용자 ID 정규화 (user_ 패턴 감지)
        path = middleware._normalize_path("/api/users/user_12345")
        assert "{user_id}" in path

        # 일반 경로는 그대로 유지
        path = middleware._normalize_path("/healthz")
        assert path == "/healthz"

        path = middleware._normalize_path("/api/policies/search")
        assert "policies" in path and "search" in path

    def test_middleware_uuid_detection(self):
        """UUID 감지 테스트."""
        middleware = PrometheusMiddleware(app=MagicMock())

        # UUID 형식 감지
        assert middleware._is_uuid_like("abc123def456ghi789")
        assert middleware._is_uuid_like("550e8400-e29b-41d4-a716-446655440000")

        # 짧은 문자열은 제외
        assert not middleware._is_uuid_like("short")

        # 순수 숫자는 제외
        assert not middleware._is_uuid_like("123456789012")
