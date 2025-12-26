"""FastAPI 인증 의존성 테스트."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.auth.dependencies import (
    get_auth_repo,
    get_current_active_user,
    get_current_user,
    get_optional_user,
    require_admin,
)
from src.auth.models import TokenData, User


class TestGetAuthRepo:
    """get_auth_repo 테스트."""

    def test_returns_auth_repository(self):
        """AuthRepository 반환."""
        repo = get_auth_repo()
        assert repo is not None

    def test_singleton(self):
        """싱글톤 패턴."""
        repo1 = get_auth_repo()
        repo2 = get_auth_repo()
        assert repo1 is repo2


class TestGetCurrentUser:
    """get_current_user 테스트."""

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self):
        """인증 정보 없으면 401."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=None, repo=MagicMock())

        assert exc_info.value.status_code == 401
        assert "인증이 필요합니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """유효하지 않은 토큰이면 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch("src.auth.dependencies.verify_token", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=credentials, repo=MagicMock())

        assert exc_info.value.status_code == 401
        assert "유효하지 않은 토큰" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self):
        """사용자를 찾을 수 없으면 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )
        token_data = TokenData(
            user_id="nonexistent_user",
            email="test@example.com",
            role="user",
        )

        mock_repo = MagicMock()
        mock_repo.get_user_by_id.return_value = None

        with patch("src.auth.dependencies.verify_token", return_value=token_data):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=credentials, repo=mock_repo)

        assert exc_info.value.status_code == 401
        assert "사용자를 찾을 수 없습니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_user_returned(self):
        """유효한 사용자 반환."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )
        token_data = TokenData(
            user_id="user_123",
            email="test@example.com",
            role="user",
        )
        expected_user = User(
            id="user_123",
            email="test@example.com",
            password_hash="hashed_password",
            role="user",
            is_active=True,
        )

        mock_repo = MagicMock()
        mock_repo.get_user_by_id.return_value = expected_user

        with patch("src.auth.dependencies.verify_token", return_value=token_data):
            user = await get_current_user(credentials=credentials, repo=mock_repo)

        assert user.id == "user_123"
        assert user.email == "test@example.com"


class TestGetCurrentActiveUser:
    """get_current_active_user 테스트."""

    @pytest.mark.asyncio
    async def test_active_user_returned(self):
        """활성 사용자 반환."""
        active_user = User(
            id="user_123",
            email="test@example.com",
            password_hash="hashed_password",
            role="user",
            is_active=True,
        )

        user = await get_current_active_user(current_user=active_user)
        assert user.id == "user_123"

    @pytest.mark.asyncio
    async def test_inactive_user_raises_403(self):
        """비활성 사용자는 403."""
        inactive_user = User(
            id="user_123",
            email="test@example.com",
            password_hash="hashed_password",
            role="user",
            is_active=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(current_user=inactive_user)

        assert exc_info.value.status_code == 403
        assert "비활성화된 계정" in exc_info.value.detail


class TestGetOptionalUser:
    """get_optional_user 테스트."""

    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        """인증 정보 없으면 None."""
        user = await get_optional_user(credentials=None, repo=MagicMock())
        assert user is None

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self):
        """유효하지 않은 토큰이면 None."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch("src.auth.dependencies.verify_token", return_value=None):
            user = await get_optional_user(credentials=credentials, repo=MagicMock())

        assert user is None

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """유효한 토큰이면 사용자 반환."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )
        token_data = TokenData(
            user_id="user_123",
            email="test@example.com",
            role="user",
        )
        expected_user = User(
            id="user_123",
            email="test@example.com",
            password_hash="hashed_password",
            role="user",
            is_active=True,
        )

        mock_repo = MagicMock()
        mock_repo.get_user_by_id.return_value = expected_user

        with patch("src.auth.dependencies.verify_token", return_value=token_data):
            user = await get_optional_user(credentials=credentials, repo=mock_repo)

        assert user is not None
        assert user.id == "user_123"


class TestRequireAdmin:
    """require_admin 테스트."""

    @pytest.mark.asyncio
    async def test_admin_user_allowed(self):
        """관리자 허용."""
        admin_user = User(
            id="admin_123",
            email="admin@example.com",
            password_hash="hashed_password",
            role="admin",
            is_active=True,
        )

        user = await require_admin(current_user=admin_user)
        assert user.role == "admin"

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self):
        """비관리자는 403."""
        regular_user = User(
            id="user_123",
            email="user@example.com",
            password_hash="hashed_password",
            role="user",
            is_active=True,
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=regular_user)

        assert exc_info.value.status_code == 403
        assert "관리자 권한이 필요합니다" in exc_info.value.detail
