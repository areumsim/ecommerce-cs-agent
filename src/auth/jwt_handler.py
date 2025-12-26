"""JWT 토큰 핸들러.

액세스 토큰과 리프레시 토큰 생성/검증을 담당합니다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .models import TokenData

logger = logging.getLogger(__name__)

# JWT 라이브러리 선택
try:
    from jose import JWTError, jwt

    USE_JOSE = True
except ImportError:
    try:
        import jwt as pyjwt
        from jwt.exceptions import PyJWTError as JWTError

        jwt = pyjwt
        USE_JOSE = False
    except ImportError:
        jwt = None
        JWTError = Exception
        USE_JOSE = False


def _get_auth_config() -> Dict[str, Any]:
    """인증 설정 로드."""
    try:
        from src.config import get_config

        config = get_config()
        raw = config.get_raw("auth")
        return raw.get("jwt", {})
    except Exception:
        return {}


def _get_secret_key() -> str:
    """시크릿 키 반환."""
    import os

    cfg = _get_auth_config()
    env_key = os.environ.get("JWT_SECRET_KEY")

    if env_key:
        return env_key

    # 환경변수 미설정 시 경고 (개발 환경용)
    logger.warning(
        "JWT_SECRET_KEY 환경변수가 설정되지 않았습니다. "
        "개발용 기본값을 사용합니다. 프로덕션에서는 반드시 환경변수를 설정하세요."
    )
    return cfg.get("secret_key", "dev-secret-key-change-in-production")


def _get_algorithm() -> str:
    """알고리즘 반환."""
    cfg = _get_auth_config()
    return cfg.get("algorithm", "HS256")


def _get_access_token_expire_minutes() -> int:
    """액세스 토큰 만료 시간 (분)."""
    cfg = _get_auth_config()
    return cfg.get("access_token_expire_minutes", 30)


def _get_refresh_token_expire_days() -> int:
    """리프레시 토큰 만료 시간 (일)."""
    cfg = _get_auth_config()
    return cfg.get("refresh_token_expire_days", 7)


def create_access_token(
    user_id: str,
    email: str,
    role: str = "user",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """액세스 토큰 생성.

    Args:
        user_id: 사용자 ID
        email: 이메일
        role: 역할 (user, admin)
        expires_delta: 만료 시간 (기본값: 설정값)

    Returns:
        JWT 액세스 토큰
    """
    if jwt is None:
        raise RuntimeError("JWT 라이브러리가 설치되지 않았습니다. python-jose 또는 PyJWT를 설치하세요.")

    if expires_delta is None:
        expires_delta = timedelta(minutes=_get_access_token_expire_minutes())

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if USE_JOSE:
        return jwt.encode(payload, _get_secret_key(), algorithm=_get_algorithm())
    else:
        return jwt.encode(payload, _get_secret_key(), algorithm=_get_algorithm())


def create_refresh_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """리프레시 토큰 생성.

    Args:
        user_id: 사용자 ID
        expires_delta: 만료 시간 (기본값: 설정값)

    Returns:
        JWT 리프레시 토큰
    """
    if jwt is None:
        raise RuntimeError("JWT 라이브러리가 설치되지 않았습니다.")

    if expires_delta is None:
        expires_delta = timedelta(days=_get_refresh_token_expire_days())

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if USE_JOSE:
        return jwt.encode(payload, _get_secret_key(), algorithm=_get_algorithm())
    else:
        return jwt.encode(payload, _get_secret_key(), algorithm=_get_algorithm())


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """토큰 검증.

    Args:
        token: JWT 토큰
        token_type: 토큰 유형 (access, refresh)

    Returns:
        토큰 데이터 (유효하면) 또는 None
    """
    if jwt is None:
        logger.error("JWT 라이브러리가 설치되지 않았습니다.")
        return None

    try:
        if USE_JOSE:
            payload = jwt.decode(token, _get_secret_key(), algorithms=[_get_algorithm()])
        else:
            payload = jwt.decode(token, _get_secret_key(), algorithms=[_get_algorithm()])

        # 토큰 타입 검증
        if payload.get("type") != token_type:
            logger.warning(f"토큰 타입 불일치: expected={token_type}, got={payload.get('type')}")
            return None

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("토큰에 사용자 ID가 없습니다.")
            return None

        return TokenData(
            user_id=user_id,
            email=payload.get("email", ""),
            role=payload.get("role", "user"),
            exp=datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc),
        )

    except JWTError as e:
        logger.warning(f"토큰 검증 실패: {e}")
        return None
    except Exception as e:
        logger.error(f"토큰 검증 중 오류: {e}")
        return None


def get_token_expiry_seconds() -> int:
    """액세스 토큰 만료 시간 (초)."""
    return _get_access_token_expire_minutes() * 60
