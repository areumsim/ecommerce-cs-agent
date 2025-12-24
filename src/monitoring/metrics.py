"""Prometheus 메트릭 정의.

에이전트 시스템의 주요 메트릭을 정의합니다.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional

from prometheus_client import Counter, Histogram, Gauge, Info

# ============================================
# HTTP 메트릭
# ============================================

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ============================================
# 에이전트 메트릭
# ============================================

AGENT_REQUESTS_TOTAL = Counter(
    "agent_requests_total",
    "Total agent requests",
    ["agent_type", "intent"],
)

AGENT_RESPONSE_TIME = Histogram(
    "agent_response_time_seconds",
    "Agent response time in seconds",
    ["agent_type"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 60.0),
)

AGENT_ERRORS_TOTAL = Counter(
    "agent_errors_total",
    "Total agent errors",
    ["agent_type", "error_type"],
)

# ============================================
# LLM 메트릭
# ============================================

LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Total LLM API calls",
    ["model", "status"],
)

LLM_TOKENS_USED = Counter(
    "llm_tokens_used_total",
    "Total LLM tokens used",
    ["model", "token_type"],  # token_type: prompt, completion
)

LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "LLM API latency in seconds",
    ["model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# ============================================
# 데이터베이스 메트릭
# ============================================

DB_QUERIES_TOTAL = Counter(
    "db_queries_total",
    "Total database queries",
    ["table", "operation"],  # operation: select, insert, update, delete
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["table", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# ============================================
# 시스템 메트릭
# ============================================

ACTIVE_CONVERSATIONS = Gauge(
    "active_conversations",
    "Number of active conversations",
)

ACTIVE_USERS = Gauge(
    "active_users",
    "Number of active users in the last hour",
)

# 앱 정보
APP_INFO = Info(
    "app",
    "Application information",
)


def set_app_info(name: str, version: str, environment: str) -> None:
    """앱 정보 설정."""
    APP_INFO.info({
        "name": name,
        "version": version,
        "environment": environment,
    })


# ============================================
# 편의 함수
# ============================================


def track_request(method: str, endpoint: str, status: int, duration: float) -> None:
    """HTTP 요청 메트릭 기록.

    Args:
        method: HTTP 메서드
        endpoint: 엔드포인트 경로
        status: HTTP 상태 코드
        duration: 요청 소요 시간 (초)
    """
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()
    HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


def track_agent_request(agent_type: str, intent: str, duration: float, error: Optional[str] = None) -> None:
    """에이전트 요청 메트릭 기록.

    Args:
        agent_type: 에이전트 유형
        intent: 의도
        duration: 처리 시간 (초)
        error: 에러 유형 (있으면)
    """
    AGENT_REQUESTS_TOTAL.labels(agent_type=agent_type, intent=intent).inc()
    AGENT_RESPONSE_TIME.labels(agent_type=agent_type).observe(duration)

    if error:
        AGENT_ERRORS_TOTAL.labels(agent_type=agent_type, error_type=error).inc()


def track_llm_request(
    model: str,
    status: str,
    latency: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """LLM 요청 메트릭 기록.

    Args:
        model: 모델명
        status: 상태 (success, error)
        latency: 지연 시간 (초)
        prompt_tokens: 프롬프트 토큰 수
        completion_tokens: 완성 토큰 수
    """
    LLM_REQUESTS_TOTAL.labels(model=model, status=status).inc()
    LLM_LATENCY.labels(model=model).observe(latency)

    if prompt_tokens > 0:
        LLM_TOKENS_USED.labels(model=model, token_type="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        LLM_TOKENS_USED.labels(model=model, token_type="completion").inc(completion_tokens)


def track_db_query(table: str, operation: str, duration: float) -> None:
    """DB 쿼리 메트릭 기록.

    Args:
        table: 테이블명
        operation: 작업 유형 (select, insert, update, delete)
        duration: 쿼리 소요 시간 (초)
    """
    DB_QUERIES_TOTAL.labels(table=table, operation=operation).inc()
    DB_QUERY_DURATION.labels(table=table, operation=operation).observe(duration)


# ============================================
# 데코레이터
# ============================================


def timed_agent(agent_type: str):
    """에이전트 실행 시간 측정 데코레이터."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = type(e).__name__
                raise
            finally:
                duration = time.time() - start_time
                intent = kwargs.get("intent", "unknown")
                track_agent_request(agent_type, intent, duration, error)

        return wrapper

    return decorator


@contextmanager
def timed_db_query(table: str, operation: str):
    """DB 쿼리 시간 측정 컨텍스트 매니저."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        track_db_query(table, operation, duration)
