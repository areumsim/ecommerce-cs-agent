"""Rate Limiter 모듈.

API 요청 제한을 위한 TokenBucket 알고리즘 구현.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TokenBucket:
    """토큰 버킷 알고리즘 구현."""

    capacity: int = 100  # 최대 토큰 수
    refill_rate: float = 10.0  # 초당 충전되는 토큰 수
    tokens: float = field(default=0.0, init=False)
    last_refill: float = field(default_factory=time.time, init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def _refill(self) -> None:
        """토큰 충전."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """토큰 소비 시도.

        Args:
            tokens: 소비할 토큰 수

        Returns:
            토큰 소비 성공 여부
        """
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_remaining(self) -> int:
        """남은 토큰 수 반환."""
        self._refill()
        return int(self.tokens)


class RateLimiter:
    """API Rate Limiter.

    클라이언트별 요청 제한을 관리합니다.
    """

    def __init__(
        self,
        capacity: int = 100,
        refill_rate: float = 10.0,
        cleanup_interval: int = 300,
    ):
        """Rate Limiter 초기화.

        Args:
            capacity: 클라이언트당 최대 토큰 수
            refill_rate: 초당 충전 토큰 수
            cleanup_interval: 비활성 버킷 정리 간격 (초)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.cleanup_interval = cleanup_interval
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def _get_bucket(self, client_id: str) -> TokenBucket:
        """클라이언트별 버킷 반환."""
        if client_id not in self._buckets:
            self._buckets[client_id] = TokenBucket(
                capacity=self.capacity,
                refill_rate=self.refill_rate,
            )
        return self._buckets[client_id]

    def _cleanup_stale_buckets(self) -> None:
        """비활성 버킷 정리."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return

        stale_threshold = now - self.cleanup_interval
        stale_keys = [
            key
            for key, bucket in self._buckets.items()
            if bucket.last_refill < stale_threshold
        ]
        for key in stale_keys:
            del self._buckets[key]
        self._last_cleanup = now

    def allow(self, client_id: str, tokens: int = 1) -> bool:
        """요청 허용 여부 확인.

        Args:
            client_id: 클라이언트 식별자 (IP 또는 사용자 ID)
            tokens: 소비할 토큰 수

        Returns:
            요청 허용 여부
        """
        with self._lock:
            self._cleanup_stale_buckets()
            bucket = self._get_bucket(client_id)
            return bucket.consume(tokens)

    def get_remaining(self, client_id: str) -> int:
        """남은 토큰 수 반환."""
        with self._lock:
            bucket = self._get_bucket(client_id)
            return bucket.get_remaining()

    def get_retry_after(self, client_id: str) -> Optional[float]:
        """재시도 가능 시간 반환 (초).

        토큰이 부족한 경우 1개 토큰이 충전되는데 필요한 시간 반환.
        """
        remaining = self.get_remaining(client_id)
        if remaining > 0:
            return None
        return 1.0 / self.refill_rate


# 전역 Rate Limiter 인스턴스
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """전역 Rate Limiter 인스턴스 반환."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def init_rate_limiter(
    capacity: int = 100,
    refill_rate: float = 10.0,
) -> RateLimiter:
    """Rate Limiter 초기화.

    Args:
        capacity: 클라이언트당 최대 토큰 수
        refill_rate: 초당 충전 토큰 수

    Returns:
        초기화된 RateLimiter 인스턴스
    """
    global _rate_limiter
    _rate_limiter = RateLimiter(capacity=capacity, refill_rate=refill_rate)
    return _rate_limiter
