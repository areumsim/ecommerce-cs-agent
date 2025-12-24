"""토큰 블랙리스트 모듈.

로그아웃된 토큰을 관리합니다.
"""

from __future__ import annotations

import time
import threading
from typing import Dict, Optional


class TokenBlacklist:
    """토큰 블랙리스트 관리.

    메모리 기반으로 블랙리스트된 토큰을 관리합니다.
    토큰 만료 시간에 따라 자동으로 정리됩니다.
    """

    def __init__(self, cleanup_interval: int = 300):
        """토큰 블랙리스트 초기화.

        Args:
            cleanup_interval: 만료된 토큰 정리 간격 (초)
        """
        self._blacklist: Dict[str, float] = {}  # {token: expiry_time}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval

    def add(self, token: str, expires_at: float) -> None:
        """토큰을 블랙리스트에 추가.

        Args:
            token: 블랙리스트에 추가할 토큰
            expires_at: 토큰 만료 시간 (Unix timestamp)
        """
        with self._lock:
            self._blacklist[token] = expires_at
            self._cleanup_expired()

    def is_blacklisted(self, token: str) -> bool:
        """토큰이 블랙리스트에 있는지 확인.

        Args:
            token: 확인할 토큰

        Returns:
            블랙리스트 여부
        """
        with self._lock:
            if token not in self._blacklist:
                return False
            # 만료된 토큰은 블랙리스트에서 제거
            if self._blacklist[token] < time.time():
                del self._blacklist[token]
                return False
            return True

    def remove(self, token: str) -> bool:
        """토큰을 블랙리스트에서 제거.

        Args:
            token: 제거할 토큰

        Returns:
            제거 성공 여부
        """
        with self._lock:
            if token in self._blacklist:
                del self._blacklist[token]
                return True
            return False

    def _cleanup_expired(self) -> None:
        """만료된 토큰 정리."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expired_tokens = [
            token for token, expiry in self._blacklist.items() if expiry < now
        ]
        for token in expired_tokens:
            del self._blacklist[token]
        self._last_cleanup = now

    def clear(self) -> None:
        """블랙리스트 초기화."""
        with self._lock:
            self._blacklist.clear()

    def count(self) -> int:
        """블랙리스트 토큰 수 반환."""
        with self._lock:
            return len(self._blacklist)


# 전역 토큰 블랙리스트 인스턴스
_token_blacklist: Optional[TokenBlacklist] = None


def get_token_blacklist() -> TokenBlacklist:
    """전역 토큰 블랙리스트 인스턴스 반환."""
    global _token_blacklist
    if _token_blacklist is None:
        _token_blacklist = TokenBlacklist()
    return _token_blacklist


def blacklist_token(token: str, expires_at: float) -> None:
    """토큰을 블랙리스트에 추가.

    Args:
        token: 블랙리스트에 추가할 토큰
        expires_at: 토큰 만료 시간 (Unix timestamp)
    """
    get_token_blacklist().add(token, expires_at)


def is_token_blacklisted(token: str) -> bool:
    """토큰이 블랙리스트에 있는지 확인.

    Args:
        token: 확인할 토큰

    Returns:
        블랙리스트 여부
    """
    return get_token_blacklist().is_blacklisted(token)
