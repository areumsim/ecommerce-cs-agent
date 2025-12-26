"""Rate Limiter 테스트."""

import time
import threading

import pytest

from src.auth.rate_limiter import (
    RateLimiter,
    TokenBucket,
    get_rate_limiter,
    init_rate_limiter,
)


class TestTokenBucket:
    """TokenBucket 테스트."""

    def test_initial_tokens(self):
        """초기 토큰 수는 용량과 동일."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        assert bucket.tokens == 100.0

    def test_consume_success(self):
        """토큰 소비 성공."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        assert bucket.consume(1) is True
        assert bucket.tokens < 100

    def test_consume_multiple(self):
        """여러 토큰 소비."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        assert bucket.consume(50) is True
        assert bucket.get_remaining() <= 50

    def test_consume_fail_not_enough(self):
        """토큰 부족 시 실패."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.tokens = 5
        assert bucket.consume(10) is False

    def test_get_remaining(self):
        """남은 토큰 수 반환."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        remaining = bucket.get_remaining()
        assert remaining == 100

    def test_refill_over_time(self):
        """시간 경과에 따른 토큰 충전."""
        bucket = TokenBucket(capacity=100, refill_rate=1000.0)  # 빠른 충전
        bucket.tokens = 0
        bucket.last_refill = time.time() - 0.1  # 0.1초 전

        bucket._refill()
        # 0.1초 * 1000 = 100 토큰 충전
        assert bucket.tokens >= 100

    def test_refill_cap_at_capacity(self):
        """용량 이상 충전 안됨."""
        bucket = TokenBucket(capacity=100, refill_rate=1000.0)
        bucket.last_refill = time.time() - 10  # 10초 전

        bucket._refill()
        assert bucket.tokens <= 100


class TestRateLimiter:
    """RateLimiter 테스트."""

    def test_allow_initial_request(self):
        """첫 요청 허용."""
        limiter = RateLimiter(capacity=100, refill_rate=10.0)
        assert limiter.allow("client1") is True

    def test_allow_multiple_clients(self):
        """여러 클라이언트 독립 처리."""
        limiter = RateLimiter(capacity=10, refill_rate=1.0)

        # 각 클라이언트별 독립적인 버킷
        assert limiter.allow("client1") is True
        assert limiter.allow("client2") is True

    def test_deny_when_exhausted(self):
        """토큰 소진 시 거부."""
        limiter = RateLimiter(capacity=2, refill_rate=0.001)

        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is False  # 소진

    def test_get_remaining(self):
        """남은 토큰 조회."""
        limiter = RateLimiter(capacity=100, refill_rate=10.0)

        limiter.allow("client1")
        remaining = limiter.get_remaining("client1")
        assert remaining <= 100

    def test_get_retry_after_when_available(self):
        """토큰 있을 때 None 반환."""
        limiter = RateLimiter(capacity=100, refill_rate=10.0)
        assert limiter.get_retry_after("new_client") is None

    def test_get_retry_after_when_exhausted(self):
        """토큰 소진 시 재시도 시간 반환."""
        limiter = RateLimiter(capacity=1, refill_rate=10.0)

        limiter.allow("client1")
        limiter.allow("client1")  # 소진

        retry_after = limiter.get_retry_after("client1")
        # 토큰 소진 시 재시도 시간 반환
        if limiter.get_remaining("client1") == 0:
            assert retry_after == pytest.approx(0.1, abs=0.01)

    def test_cleanup_stale_buckets(self):
        """비활성 버킷 정리."""
        limiter = RateLimiter(capacity=100, refill_rate=10.0, cleanup_interval=0)

        limiter.allow("stale_client")
        # last_refill을 과거로 설정
        limiter._buckets["stale_client"].last_refill = time.time() - 1000
        limiter._last_cleanup = 0

        # 새 요청 시 정리 트리거
        limiter.allow("new_client")

        # stale_client 버킷이 정리됨
        assert "stale_client" not in limiter._buckets


class TestGlobalFunctions:
    """전역 함수 테스트."""

    def test_get_rate_limiter_singleton(self):
        """싱글톤 인스턴스."""
        rl1 = get_rate_limiter()
        rl2 = get_rate_limiter()
        assert rl1 is rl2

    def test_init_rate_limiter(self):
        """Rate Limiter 초기화."""
        limiter = init_rate_limiter(capacity=50, refill_rate=5.0)
        assert limiter.capacity == 50
        assert limiter.refill_rate == 5.0


class TestConcurrency:
    """동시성 테스트."""

    def test_concurrent_requests(self):
        """동시 요청 처리."""
        limiter = RateLimiter(capacity=100, refill_rate=10.0)
        allowed_count = 0
        lock = threading.Lock()

        def make_requests(client_id, count):
            nonlocal allowed_count
            for _ in range(count):
                if limiter.allow(client_id):
                    with lock:
                        allowed_count += 1

        threads = [
            threading.Thread(target=make_requests, args=(f"client_{i}", 10))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 각 클라이언트가 100개 용량이므로 모두 허용
        assert allowed_count == 50

    def test_single_client_concurrent(self):
        """단일 클라이언트 동시 요청."""
        limiter = RateLimiter(capacity=20, refill_rate=0.0)
        allowed_count = 0
        lock = threading.Lock()

        def make_requests(count):
            nonlocal allowed_count
            for _ in range(count):
                if limiter.allow("single_client"):
                    with lock:
                        allowed_count += 1

        threads = [
            threading.Thread(target=make_requests, args=(10,))
            for _ in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 용량 20이고 충전 없으므로 최대 20개만 허용
        assert allowed_count <= 20
