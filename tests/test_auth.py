"""인증 모듈 테스트."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.auth.models import User, UserCreate, UserLogin, TokenData, TokenResponse
from src.auth.password import hash_password, verify_password
from src.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from src.auth.repository import AuthRepository


class TestPasswordHashing:
    """비밀번호 해싱 테스트."""

    def test_hash_password_returns_different_hash(self):
        """같은 비밀번호도 다른 해시 생성."""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # salt 때문에 다름
        assert hash1 != password
        assert hash2 != password

    def test_verify_password_correct(self):
        """올바른 비밀번호 검증."""
        password = "secure_password_456"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """틀린 비밀번호 검증 실패."""
        password = "secure_password_456"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_password_length(self):
        """해시 길이 확인 (bcrypt 표준)."""
        password = "test"
        hashed = hash_password(password)

        assert len(hashed) == 60  # bcrypt 표준 길이


class TestJWTHandler:
    """JWT 핸들러 테스트."""

    def test_create_access_token(self):
        """액세스 토큰 생성."""
        token = create_access_token(
            user_id="user_123",
            email="test@example.com",
            role="user"
        )

        assert isinstance(token, str)
        assert len(token) > 50

    def test_create_refresh_token(self):
        """리프레시 토큰 생성."""
        token = create_refresh_token(user_id="user_123")

        assert isinstance(token, str)
        assert len(token) > 50

    def test_verify_access_token(self):
        """액세스 토큰 검증."""
        token = create_access_token(
            user_id="user_456",
            email="verify@example.com",
            role="admin"
        )

        token_data = verify_token(token, token_type="access")

        assert token_data is not None
        assert token_data.user_id == "user_456"
        assert token_data.email == "verify@example.com"
        assert token_data.role == "admin"

    def test_verify_refresh_token(self):
        """리프레시 토큰 검증."""
        token = create_refresh_token(user_id="user_789")

        token_data = verify_token(token, token_type="refresh")

        assert token_data is not None
        assert token_data.user_id == "user_789"

    def test_verify_expired_token(self):
        """만료된 토큰 검증 실패."""
        token = create_access_token(
            user_id="user_123",
            email="test@example.com",
            expires_delta=timedelta(seconds=-1)  # 이미 만료
        )

        token_data = verify_token(token, token_type="access")

        assert token_data is None

    def test_verify_invalid_token(self):
        """유효하지 않은 토큰."""
        invalid_token = "invalid.token.here"

        token_data = verify_token(invalid_token, token_type="access")

        assert token_data is None


class TestUserModels:
    """사용자 모델 테스트."""

    def test_user_create_validation(self):
        """UserCreate 모델 검증."""
        user = UserCreate(
            email="test@example.com",
            password="password123",
            name="Test User"
        )

        assert user.email == "test@example.com"
        assert user.password == "password123"
        assert user.name == "Test User"

    def test_user_create_email_validation(self):
        """이메일 형식 검증."""
        with pytest.raises(ValueError):
            UserCreate(
                email="invalid-email",
                password="password123"
            )

    def test_user_create_password_min_length(self):
        """비밀번호 최소 길이 검증."""
        with pytest.raises(ValueError):
            UserCreate(
                email="test@example.com",
                password="short"  # 8자 미만
            )

    def test_user_login_model(self):
        """UserLogin 모델."""
        login = UserLogin(
            email="login@example.com",
            password="password123"
        )

        assert login.email == "login@example.com"
        assert login.password == "password123"

    def test_token_response_model(self):
        """TokenResponse 모델."""
        response = TokenResponse(
            access_token="access_token_here",
            refresh_token="refresh_token_here",
            token_type="bearer",
            expires_in=3600
        )

        assert response.access_token == "access_token_here"
        assert response.token_type == "bearer"
        assert response.expires_in == 3600


class TestAuthRepository:
    """인증 저장소 테스트."""

    @pytest.fixture
    def repo(self, tmp_path):
        """테스트용 저장소."""
        db_path = str(tmp_path / "test_auth.db")
        return AuthRepository(db_path=db_path)

    def test_create_user(self, repo):
        """사용자 생성."""
        user = repo.create_user(
            email="new@example.com",
            password="password123",  # 평문 비밀번호
            name="New User"
        )

        assert user is not None
        assert user.email == "new@example.com"
        assert user.name == "New User"
        assert user.is_active is True
        assert user.id.startswith("user_")

    def test_get_user_by_email(self, repo):
        """이메일로 사용자 조회."""
        repo.create_user(
            email="find@example.com",
            password="password123"
        )

        user = repo.get_user_by_email("find@example.com")

        assert user is not None
        assert user.email == "find@example.com"

    def test_get_user_by_email_not_found(self, repo):
        """존재하지 않는 사용자."""
        user = repo.get_user_by_email("notfound@example.com")

        assert user is None

    def test_get_user_by_id(self, repo):
        """ID로 사용자 조회."""
        created = repo.create_user(
            email="byid@example.com",
            password="password123"
        )

        user = repo.get_user_by_id(created.id)

        assert user is not None
        assert user.id == created.id
        assert user.email == "byid@example.com"

    def test_duplicate_email_raises_error(self, repo):
        """중복 이메일 시 ValueError 발생."""
        repo.create_user(
            email="dup@example.com",
            password="password123"
        )

        with pytest.raises(ValueError, match="이미 존재하는 이메일"):
            repo.create_user(
                email="dup@example.com",
                password="password456"
            )
