"""인증 모듈.

JWT 기반 사용자 인증/인가를 제공합니다.
"""

from .models import User, TokenData, UserCreate, UserLogin, TokenResponse
from .jwt_handler import create_access_token, create_refresh_token, verify_token
from .password import hash_password, verify_password
from .dependencies import get_current_user, get_current_active_user, get_optional_user, get_auth_repo
from .repository import AuthRepository
from .rate_limiter import RateLimiter, get_rate_limiter, init_rate_limiter
from .token_blacklist import TokenBlacklist, get_token_blacklist, blacklist_token, is_token_blacklisted

__all__ = [
    "User",
    "TokenData",
    "UserCreate",
    "UserLogin",
    "TokenResponse",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "hash_password",
    "verify_password",
    "get_current_user",
    "get_current_active_user",
    "get_optional_user",
    "get_auth_repo",
    "AuthRepository",
    # Rate Limiter
    "RateLimiter",
    "get_rate_limiter",
    "init_rate_limiter",
    # Token Blacklist
    "TokenBlacklist",
    "get_token_blacklist",
    "blacklist_token",
    "is_token_blacklisted",
]
