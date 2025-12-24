"""인증 저장소.

사용자 및 토큰 데이터의 CRUD 작업을 담당합니다.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from .models import RefreshToken, User
from .password import hash_password

logger = logging.getLogger(__name__)


def _get_db_path() -> Path:
    """데이터베이스 경로 반환."""
    try:
        from src.config import get_config

        config = get_config()
        return Path(config.paths.sqlite_path)
    except Exception:
        return Path("data/ecommerce.db")


class AuthRepository:
    """인증 저장소."""

    def __init__(self, db_path: Optional[Path] = None):
        """초기화.

        Args:
            db_path: 데이터베이스 경로 (없으면 설정에서 로드)
        """
        self.db_path = db_path or _get_db_path()
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """DB 연결."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """테이블 생성."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # users_auth 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users_auth (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT,
                    role TEXT DEFAULT 'user',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            # refresh_tokens 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT,
                    revoked INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users_auth(id)
                )
            """)

            # 인덱스
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_auth_email ON users_auth(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON refresh_tokens(token)")

            conn.commit()
            logger.info("인증 테이블 초기화 완료")
        finally:
            conn.close()

    # ============================================
    # 사용자 CRUD
    # ============================================

    def create_user(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        role: str = "user",
    ) -> User:
        """사용자 생성.

        Args:
            email: 이메일
            password: 평문 비밀번호
            name: 이름
            role: 역할

        Returns:
            생성된 사용자

        Raises:
            ValueError: 이미 존재하는 이메일
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # 중복 체크
            cursor.execute("SELECT id FROM users_auth WHERE email = ?", (email,))
            if cursor.fetchone():
                raise ValueError(f"이미 존재하는 이메일입니다: {email}")

            user_id = f"user_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()
            password_hash = hash_password(password)

            cursor.execute(
                """
                INSERT INTO users_auth (id, email, password_hash, name, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (user_id, email, password_hash, name, role, now, now),
            )
            conn.commit()

            logger.info(f"사용자 생성: {user_id} ({email})")

            return User(
                id=user_id,
                email=email,
                password_hash=password_hash,
                name=name,
                role=role,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        finally:
            conn.close()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """ID로 사용자 조회."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users_auth WHERE id = ?", (user_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                name=row["name"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users_auth WHERE email = ?", (email,))
            row = cursor.fetchone()

            if not row:
                return None

            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                name=row["name"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        finally:
            conn.close()

    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """사용자 정보 업데이트."""
        allowed_fields = {"name", "role", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return self.get_user_by_id(user_id)

        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [user_id]

            cursor.execute(f"UPDATE users_auth SET {set_clause} WHERE id = ?", values)
            conn.commit()

            return self.get_user_by_id(user_id)
        finally:
            conn.close()

    def deactivate_user(self, user_id: str) -> bool:
        """사용자 비활성화."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "UPDATE users_auth SET is_active = 0, updated_at = ? WHERE id = ?",
                (now, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ============================================
    # 리프레시 토큰 관리
    # ============================================

    def save_refresh_token(
        self,
        user_id: str,
        token: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """리프레시 토큰 저장."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            token_id = f"rt_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc).isoformat()
            expires_str = expires_at.isoformat()

            cursor.execute(
                """
                INSERT INTO refresh_tokens (id, user_id, token, expires_at, created_at, revoked)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (token_id, user_id, token, expires_str, now),
            )
            conn.commit()

            return RefreshToken(
                id=token_id,
                user_id=user_id,
                token=token,
                expires_at=expires_str,
                created_at=now,
                revoked=False,
            )
        finally:
            conn.close()

    def get_refresh_token(self, token: str) -> Optional[RefreshToken]:
        """리프레시 토큰 조회."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM refresh_tokens WHERE token = ? AND revoked = 0",
                (token,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return RefreshToken(
                id=row["id"],
                user_id=row["user_id"],
                token=row["token"],
                expires_at=row["expires_at"],
                created_at=row["created_at"],
                revoked=bool(row["revoked"]),
            )
        finally:
            conn.close()

    def revoke_refresh_token(self, token: str) -> bool:
        """리프레시 토큰 무효화."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE token = ?",
                (token,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """사용자의 모든 토큰 무효화."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def cleanup_expired_tokens(self) -> int:
        """만료된 토큰 정리."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "DELETE FROM refresh_tokens WHERE expires_at < ? OR revoked = 1",
                (now,),
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"만료된 토큰 {deleted}개 삭제")
            return deleted
        finally:
            conn.close()
