"""FastAPI 인증 의존성.

API 엔드포인트에서 사용하는 인증 관련 의존성을 정의합니다.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .jwt_handler import verify_token
from .models import TokenData, User
from .repository import AuthRepository

logger = logging.getLogger(__name__)

# Bearer 토큰 스키마
security = HTTPBearer(auto_error=False)

# 저장소 싱글톤
_auth_repo: Optional[AuthRepository] = None


def get_auth_repo() -> AuthRepository:
    """인증 저장소 반환."""
    global _auth_repo
    if _auth_repo is None:
        _auth_repo = AuthRepository()
    return _auth_repo


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    repo: AuthRepository = Depends(get_auth_repo),
) -> User:
    """현재 인증된 사용자 반환.

    Args:
        credentials: Bearer 토큰
        repo: 인증 저장소

    Returns:
        인증된 사용자

    Raises:
        HTTPException: 인증 실패
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_token(credentials.credentials, token_type="access")

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = repo.get_user_by_id(token_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """현재 활성 사용자 반환.

    비활성화된 사용자는 접근 불가.

    Args:
        current_user: 현재 사용자

    Returns:
        활성 사용자

    Raises:
        HTTPException: 비활성화된 사용자
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    repo: AuthRepository = Depends(get_auth_repo),
) -> Optional[User]:
    """선택적 인증 (토큰이 없어도 OK).

    토큰이 있으면 검증, 없으면 None 반환.

    Args:
        credentials: Bearer 토큰 (선택적)
        repo: 인증 저장소

    Returns:
        인증된 사용자 또는 None
    """
    if not credentials:
        return None

    token_data = verify_token(credentials.credentials, token_type="access")

    if not token_data:
        return None

    return repo.get_user_by_id(token_data.user_id)


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """관리자 권한 요구.

    Args:
        current_user: 현재 활성 사용자

    Returns:
        관리자 사용자

    Raises:
        HTTPException: 관리자 아님
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다",
        )
    return current_user
