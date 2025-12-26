"""토큰 블랙리스트 테스트."""

import time

import pytest

from src.auth.token_blacklist import (
    TokenBlacklist,
    blacklist_token,
    get_token_blacklist,
    is_token_blacklisted,
)


class TestTokenBlacklist:
    """TokenBlacklist 클래스 테스트."""

    def test_add_and_check(self):
        """토큰 추가 및 확인."""
        bl = TokenBlacklist()
        future_time = time.time() + 3600  # 1시간 후

        bl.add("token123", future_time)
        assert bl.is_blacklisted("token123") is True

    def test_not_blacklisted(self):
        """블랙리스트에 없는 토큰."""
        bl = TokenBlacklist()
        assert bl.is_blacklisted("nonexistent") is False

    def test_expired_token_auto_removed(self):
        """만료된 토큰 자동 제거."""
        bl = TokenBlacklist()
        past_time = time.time() - 1  # 이미 만료됨

        bl.add("expired_token", past_time)
        # 확인 시 만료된 토큰은 False 반환 및 제거
        assert bl.is_blacklisted("expired_token") is False

    def test_remove_token(self):
        """토큰 제거."""
        bl = TokenBlacklist()
        future_time = time.time() + 3600

        bl.add("to_remove", future_time)
        assert bl.remove("to_remove") is True
        assert bl.is_blacklisted("to_remove") is False

    def test_remove_nonexistent(self):
        """존재하지 않는 토큰 제거."""
        bl = TokenBlacklist()
        assert bl.remove("nonexistent") is False

    def test_clear(self):
        """블랙리스트 초기화."""
        bl = TokenBlacklist()
        future_time = time.time() + 3600

        bl.add("token1", future_time)
        bl.add("token2", future_time)
        bl.clear()

        assert bl.count() == 0

    def test_count(self):
        """토큰 수 반환."""
        bl = TokenBlacklist()
        future_time = time.time() + 3600

        assert bl.count() == 0
        bl.add("token1", future_time)
        assert bl.count() == 1
        bl.add("token2", future_time)
        assert bl.count() == 2

    def test_cleanup_expired_on_add(self):
        """추가 시 만료된 토큰 정리 (cleanup_interval 후)."""
        bl = TokenBlacklist(cleanup_interval=0)  # 즉시 정리
        past_time = time.time() - 100
        future_time = time.time() + 3600

        bl.add("expired", past_time)
        bl._last_cleanup = 0  # 강제로 정리 트리거
        bl.add("valid", future_time)

        # 만료된 토큰은 정리됨
        assert bl.is_blacklisted("expired") is False
        assert bl.is_blacklisted("valid") is True


class TestGlobalFunctions:
    """전역 함수 테스트."""

    def test_get_token_blacklist_singleton(self):
        """싱글톤 인스턴스 반환."""
        bl1 = get_token_blacklist()
        bl2 = get_token_blacklist()
        assert bl1 is bl2

    def test_blacklist_token_function(self):
        """blacklist_token 함수."""
        future_time = time.time() + 3600
        token = f"global_test_{time.time()}"

        blacklist_token(token, future_time)
        assert is_token_blacklisted(token) is True

    def test_is_token_blacklisted_function(self):
        """is_token_blacklisted 함수."""
        # 존재하지 않는 토큰
        assert is_token_blacklisted(f"not_exist_{time.time()}") is False


class TestThreadSafety:
    """스레드 안전성 테스트."""

    def test_concurrent_add_and_check(self):
        """동시 추가 및 확인."""
        import threading

        bl = TokenBlacklist()
        future_time = time.time() + 3600
        results = []

        def add_tokens(prefix, count):
            for i in range(count):
                bl.add(f"{prefix}_{i}", future_time)
                results.append(bl.is_blacklisted(f"{prefix}_{i}"))

        threads = [
            threading.Thread(target=add_tokens, args=(f"thread_{i}", 10))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 모든 결과가 True여야 함
        assert all(results)
        assert bl.count() == 50
