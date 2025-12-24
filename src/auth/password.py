"""비밀번호 해싱 유틸리티.

bcrypt 알고리즘을 사용한 안전한 비밀번호 해싱을 제공합니다.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Tuple

# bcrypt가 설치되어 있으면 사용, 아니면 fallback
try:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    USE_PASSLIB = True
except ImportError:
    pwd_context = None
    USE_PASSLIB = False


def hash_password(password: str) -> str:
    """비밀번호 해싱.

    Args:
        password: 평문 비밀번호

    Returns:
        해시된 비밀번호
    """
    if USE_PASSLIB:
        return pwd_context.hash(password)

    # Fallback: SHA-256 + salt (개발용, 프로덕션에서는 bcrypt 권장)
    salt = secrets.token_hex(16)
    hash_value = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hash_value}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증.

    Args:
        plain_password: 평문 비밀번호
        hashed_password: 해시된 비밀번호

    Returns:
        일치 여부
    """
    if USE_PASSLIB:
        return pwd_context.verify(plain_password, hashed_password)

    # Fallback: SHA-256 + salt
    if "$" not in hashed_password:
        return False
    salt, stored_hash = hashed_password.split("$", 1)
    check_hash = hashlib.sha256((plain_password + salt).encode()).hexdigest()
    return secrets.compare_digest(check_hash, stored_hash)


def generate_random_password(length: int = 16) -> str:
    """랜덤 비밀번호 생성.

    Args:
        length: 비밀번호 길이

    Returns:
        랜덤 비밀번호
    """
    return secrets.token_urlsafe(length)
