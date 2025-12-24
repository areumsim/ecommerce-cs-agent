"""인증 모델 정의.

사용자, 토큰 등 인증 관련 데이터 모델을 정의합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ============================================
# Pydantic 모델 (API 요청/응답)
# ============================================


class UserCreate(BaseModel):
    """회원가입 요청."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None


class UserLogin(BaseModel):
    """로그인 요청."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """토큰 응답."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 초 단위


class RefreshRequest(BaseModel):
    """토큰 갱신 요청."""

    refresh_token: str


class UserResponse(BaseModel):
    """사용자 정보 응답."""

    id: str
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    created_at: str


# ============================================
# 데이터클래스 (내부 사용)
# ============================================


@dataclass
class User:
    """사용자 모델."""

    id: str
    email: str
    password_hash: str
    role: str = "user"  # user, admin
    name: Optional[str] = None
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

    def to_response(self) -> UserResponse:
        """응답용 데이터로 변환."""
        return UserResponse(
            id=self.id,
            email=self.email,
            name=self.name,
            role=self.role,
            is_active=self.is_active,
            created_at=self.created_at,
        )


@dataclass
class TokenData:
    """JWT 토큰 데이터."""

    user_id: str
    email: str
    role: str = "user"
    exp: Optional[datetime] = None


@dataclass
class RefreshToken:
    """리프레시 토큰."""

    id: str
    user_id: str
    token: str
    expires_at: str
    created_at: str
    revoked: bool = False
