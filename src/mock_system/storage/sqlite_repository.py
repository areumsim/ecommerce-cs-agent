"""SQLite 기반 저장소 구현.

CSV 저장소와 동일한 인터페이스를 제공하면서
더 나은 성능과 동시성을 지원합니다.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .interfaces import Repository


@dataclass
class SqliteRepoConfig:
    """SQLite 저장소 설정."""
    db_path: str
    table_name: str
    key_field: str
    json_fields: Optional[List[str]] = None


class SqliteRepository(Repository):
    """SQLite 기반 저장소.

    특징:
    - 스레드 안전 (connection per thread)
    - 트랜잭션 지원
    - 인덱스 자동 생성
    - JSON 필드 자동 직렬화
    """

    _local = threading.local()

    def __init__(self, config: SqliteRepoConfig):
        self.config = config
        self._ensure_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """스레드별 연결 반환."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.config.db_path,
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        yield self._local.conn

    def _ensure_db(self) -> None:
        """데이터베이스 파일과 디렉토리 생성."""
        db_path = Path(self.config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    def _serialize_value(self, key: str, value: Any) -> Any:
        """값 직렬화 (JSON 필드 처리)."""
        if self.config.json_fields and key in self.config.json_fields:
            if not isinstance(value, str):
                return json.dumps(value, ensure_ascii=False)
        return value

    def _deserialize_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Row를 딕셔너리로 변환하고 JSON 필드 역직렬화."""
        result = dict(row)
        if self.config.json_fields:
            for jf in self.config.json_fields:
                if jf in result and result[jf]:
                    try:
                        result[jf] = json.loads(result[jf])
                    except (json.JSONDecodeError, TypeError):
                        pass
        return result

    def get_by_id(self, _id: str) -> Optional[Dict[str, Any]]:
        """ID로 레코드 조회."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.config.table_name} WHERE {self.config.key_field} = ?",
                (_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._deserialize_row(row)

    def query(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """필터 조건으로 레코드 조회."""
        with self._get_connection() as conn:
            if not filters:
                cursor = conn.execute(f"SELECT * FROM {self.config.table_name}")
            else:
                conditions = " AND ".join(f"{k} = ?" for k in filters.keys())
                values = list(filters.values())
                cursor = conn.execute(
                    f"SELECT * FROM {self.config.table_name} WHERE {conditions}",
                    values
                )

            return [self._deserialize_row(row) for row in cursor.fetchall()]

    def create(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """새 레코드 생성."""
        key = record.get(self.config.key_field)
        if not key:
            raise ValueError(f"Missing key_field: {self.config.key_field}")

        # 기존 레코드 확인
        existing = self.get_by_id(str(key))
        if existing:
            raise ValueError(f"Duplicate key: {key}")

        # 값 직렬화
        serialized = {
            k: self._serialize_value(k, v)
            for k, v in record.items()
        }

        columns = ", ".join(serialized.keys())
        placeholders = ", ".join("?" for _ in serialized)
        values = list(serialized.values())

        with self._get_connection() as conn:
            conn.execute(
                f"INSERT INTO {self.config.table_name} ({columns}) VALUES ({placeholders})",
                values
            )
            conn.commit()

        return record

    def update(self, _id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """레코드 업데이트."""
        existing = self.get_by_id(_id)
        if existing is None:
            raise KeyError(_id)

        # 값 직렬화
        serialized = {
            k: self._serialize_value(k, v)
            for k, v in patch.items()
        }

        set_clause = ", ".join(f"{k} = ?" for k in serialized.keys())
        values = list(serialized.values()) + [_id]

        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE {self.config.table_name} SET {set_clause} WHERE {self.config.key_field} = ?",
                values
            )
            conn.commit()

        # 업데이트된 레코드 반환
        return self.get_by_id(_id) or {}

    def delete(self, _id: str) -> None:
        """레코드 삭제."""
        with self._get_connection() as conn:
            conn.execute(
                f"DELETE FROM {self.config.table_name} WHERE {self.config.key_field} = ?",
                (_id,)
            )
            conn.commit()

    def count(self) -> int:
        """레코드 수 반환."""
        with self._get_connection() as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {self.config.table_name}")
            return cursor.fetchone()[0]

    def close(self) -> None:
        """연결 종료."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class SqliteDatabase:
    """SQLite 데이터베이스 관리자.

    스키마 생성, 마이그레이션, 저장소 관리를 담당합니다.
    """

    SCHEMA = """
    -- 사용자 테이블
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        membership_level TEXT,
        created_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

    -- 주문 테이블
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        user_id TEXT,
        status TEXT,
        order_date TEXT,
        delivery_date TEXT,
        total_amount TEXT,
        shipping_address TEXT,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);

    -- 주문 아이템 테이블
    CREATE TABLE IF NOT EXISTS order_items (
        id TEXT PRIMARY KEY,
        order_id TEXT,
        product_id TEXT,
        quantity TEXT,
        unit_price TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products_cache(product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

    -- 상품 캐시 테이블
    CREATE TABLE IF NOT EXISTS products_cache (
        product_id TEXT PRIMARY KEY,
        title TEXT,
        brand TEXT,
        category TEXT,
        price TEXT,
        image_url TEXT,
        avg_rating TEXT,
        stock_quantity TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_products_category ON products_cache(category);
    CREATE INDEX IF NOT EXISTS idx_products_brand ON products_cache(brand);

    -- 지원 티켓 테이블
    CREATE TABLE IF NOT EXISTS support_tickets (
        ticket_id TEXT PRIMARY KEY,
        user_id TEXT,
        order_id TEXT,
        issue_type TEXT,
        description TEXT,
        status TEXT,
        priority TEXT,
        created_at TEXT,
        resolved_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    );
    CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON support_tickets(user_id);
    CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status);
    CREATE INDEX IF NOT EXISTS idx_tickets_issue_type ON support_tickets(issue_type);

    -- 장바구니 테이블
    CREATE TABLE IF NOT EXISTS cart (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        product_id TEXT,
        quantity TEXT,
        added_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (product_id) REFERENCES products_cache(product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id);

    -- 위시리스트 테이블
    CREATE TABLE IF NOT EXISTS wishlist (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        product_id TEXT,
        added_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (product_id) REFERENCES products_cache(product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_wishlist_user_id ON wishlist(user_id);

    -- 대화 테이블
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        messages TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """스키마 생성."""
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(self.SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def get_repository(
        self,
        table_name: str,
        key_field: str,
        json_fields: Optional[List[str]] = None,
    ) -> SqliteRepository:
        """테이블용 저장소 생성."""
        config = SqliteRepoConfig(
            db_path=self.db_path,
            table_name=table_name,
            key_field=key_field,
            json_fields=json_fields,
        )
        return SqliteRepository(config)

    def users(self) -> SqliteRepository:
        return self.get_repository("users", "user_id")

    def orders(self) -> SqliteRepository:
        return self.get_repository("orders", "order_id")

    def order_items(self) -> SqliteRepository:
        return self.get_repository("order_items", "id")

    def products_cache(self) -> SqliteRepository:
        return self.get_repository("products_cache", "product_id")

    def support_tickets(self) -> SqliteRepository:
        return self.get_repository("support_tickets", "ticket_id")

    def cart(self) -> SqliteRepository:
        return self.get_repository("cart", "id")

    def wishlist(self) -> SqliteRepository:
        return self.get_repository("wishlist", "id")

    def conversations(self) -> SqliteRepository:
        return self.get_repository("conversations", "id", json_fields=["messages"])

    def get_stats(self) -> Dict[str, int]:
        """테이블별 레코드 수 반환."""
        tables = [
            "users", "orders", "order_items", "products_cache",
            "support_tickets", "cart", "wishlist", "conversations"
        ]
        stats = {}
        conn = sqlite3.connect(self.db_path)
        try:
            for table in tables:
                try:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[table] = 0
        finally:
            conn.close()
        return stats
