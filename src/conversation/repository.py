"""대화 저장소.

대화 세션 및 메시지의 CRUD 작업을 담당합니다.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Conversation, Message

logger = logging.getLogger(__name__)


def _get_db_path() -> Path:
    """데이터베이스 경로 반환."""
    try:
        from src.config import get_config

        config = get_config()
        return Path(config.paths.sqlite_path)
    except Exception:
        return Path("data/ecommerce.db")


class ConversationRepository:
    """대화 저장소."""

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
        """테이블 생성 및 스키마 마이그레이션."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # conversations 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    status TEXT DEFAULT 'active',
                    metadata TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT
                )
            """)

            # 스키마 마이그레이션: 기존 테이블에 status 컬럼이 없으면 추가
            cursor.execute("PRAGMA table_info(conversations)")
            columns = {row[1] for row in cursor.fetchall()}
            if "status" not in columns:
                logger.info("conversations 테이블에 status 컬럼 추가 (마이그레이션)")
                cursor.execute("ALTER TABLE conversations ADD COLUMN status TEXT DEFAULT 'active'")

            # messages 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    intent TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)

            # 인덱스
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")

            conn.commit()
            logger.info("대화 테이블 초기화 완료")
        finally:
            conn.close()

    # ============================================
    # 대화 CRUD
    # ============================================

    def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_hours: int = 24,
    ) -> Conversation:
        """대화 생성.

        Args:
            user_id: 사용자 ID
            title: 대화 제목
            metadata: 메타데이터
            expires_hours: 만료 시간 (시간)

        Returns:
            생성된 대화
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            conv_id = f"conv_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(hours=expires_hours)

            cursor.execute(
                """
                INSERT INTO conversations (id, user_id, title, status, metadata, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    conv_id,
                    user_id,
                    title,
                    json.dumps(metadata) if metadata else None,
                    now.isoformat(),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()

            logger.info(f"대화 생성: {conv_id} (user={user_id})")

            return Conversation(
                id=conv_id,
                user_id=user_id,
                title=title,
                status="active",
                metadata=metadata or {},
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
                expires_at=expires_at.isoformat(),
                messages=[],
            )
        finally:
            conn.close()

    def get_conversation(
        self,
        conversation_id: str,
        include_messages: bool = True,
    ) -> Optional[Conversation]:
        """대화 조회.

        Args:
            conversation_id: 대화 ID
            include_messages: 메시지 포함 여부

        Returns:
            대화 (없으면 None)
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()

            if not row:
                return None

            conversation = Conversation(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                status=row["status"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                expires_at=row["expires_at"],
                messages=[],
            )

            if include_messages:
                conversation.messages = self.get_messages(conversation_id)

            return conversation
        finally:
            conn.close()

    def get_user_conversations(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Conversation]:
        """사용자의 대화 목록 조회.

        Args:
            user_id: 사용자 ID
            status: 상태 필터 (active, closed, expired)
            limit: 최대 개수

        Returns:
            대화 목록 (메시지 미포함)
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    """
                    SELECT * FROM conversations
                    WHERE user_id = ? AND status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (user_id, status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM conversations
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                )

            conversations = []
            for row in cursor.fetchall():
                conversations.append(
                    Conversation(
                        id=row["id"],
                        user_id=row["user_id"],
                        title=row["title"],
                        status=row["status"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        expires_at=row["expires_at"],
                        messages=[],  # 목록에서는 메시지 미포함
                    )
                )

            return conversations
        finally:
            conn.close()

    def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Conversation]:
        """대화 업데이트.

        Args:
            conversation_id: 대화 ID
            title: 새 제목
            status: 새 상태
            metadata: 새 메타데이터

        Returns:
            업데이트된 대화
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            updates = []
            values = []

            if title is not None:
                updates.append("title = ?")
                values.append(title)

            if status is not None:
                updates.append("status = ?")
                values.append(status)

            if metadata is not None:
                updates.append("metadata = ?")
                values.append(json.dumps(metadata))

            if not updates:
                return self.get_conversation(conversation_id)

            updates.append("updated_at = ?")
            values.append(datetime.now(timezone.utc).isoformat())
            values.append(conversation_id)

            cursor.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            conn.commit()

            return self.get_conversation(conversation_id)
        finally:
            conn.close()

    def close_conversation(self, conversation_id: str) -> bool:
        """대화 종료.

        Args:
            conversation_id: 대화 ID

        Returns:
            성공 여부
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "UPDATE conversations SET status = 'closed', updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        """대화 삭제 (메시지 포함).

        Args:
            conversation_id: 대화 ID

        Returns:
            성공 여부
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # 메시지 먼저 삭제
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))

            # 대화 삭제
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

            conn.commit()
            deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"대화 삭제: {conversation_id}")

            return deleted
        finally:
            conn.close()

    # ============================================
    # 메시지 CRUD
    # ============================================

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        intent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """메시지 추가.

        Args:
            conversation_id: 대화 ID
            role: 역할 (user, assistant, system)
            content: 메시지 내용
            intent: 의도 (있으면)
            metadata: 메타데이터

        Returns:
            생성된 메시지
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, intent, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    intent,
                    json.dumps(metadata) if metadata else None,
                    now,
                ),
            )

            # 대화 업데이트 시간 갱신
            cursor.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

            conn.commit()

            return Message(
                id=msg_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                intent=intent,
                metadata=metadata or {},
                created_at=now,
            )
        finally:
            conn.close()

    def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """대화의 메시지 조회.

        Args:
            conversation_id: 대화 ID
            limit: 최대 개수 (없으면 전체)

        Returns:
            메시지 목록 (시간순)
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            if limit:
                cursor.execute(
                    """
                    SELECT * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (conversation_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                    """,
                    (conversation_id,),
                )

            messages = []
            for row in cursor.fetchall():
                messages.append(
                    Message(
                        id=row["id"],
                        conversation_id=row["conversation_id"],
                        role=row["role"],
                        content=row["content"],
                        intent=row["intent"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        created_at=row["created_at"],
                    )
                )

            return messages
        finally:
            conn.close()

    # ============================================
    # 유지보수
    # ============================================

    def expire_old_conversations(self) -> int:
        """만료된 대화 상태 업데이트.

        Returns:
            업데이트된 대화 수
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                UPDATE conversations
                SET status = 'expired', updated_at = ?
                WHERE status = 'active' AND expires_at < ?
                """,
                (now, now),
            )
            conn.commit()
            expired = cursor.rowcount
            if expired > 0:
                logger.info(f"만료된 대화 {expired}개 업데이트")
            return expired
        finally:
            conn.close()

    def cleanup_old_conversations(self, days: int = 30) -> int:
        """오래된 대화 삭제.

        Args:
            days: 보관 기간 (일)

        Returns:
            삭제된 대화 수
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            # 오래된 대화 ID 조회
            cursor.execute(
                "SELECT id FROM conversations WHERE updated_at < ?",
                (cutoff,),
            )
            old_ids = [row["id"] for row in cursor.fetchall()]

            if not old_ids:
                return 0

            # 메시지 삭제
            placeholders = ",".join("?" * len(old_ids))
            cursor.execute(
                f"DELETE FROM messages WHERE conversation_id IN ({placeholders})",
                old_ids,
            )

            # 대화 삭제
            cursor.execute(
                f"DELETE FROM conversations WHERE id IN ({placeholders})",
                old_ids,
            )

            conn.commit()
            logger.info(f"오래된 대화 {len(old_ids)}개 삭제")
            return len(old_ids)
        finally:
            conn.close()
