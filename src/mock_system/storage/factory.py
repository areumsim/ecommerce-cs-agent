"""저장소 팩토리.

설정에 따라 CSV 또는 SQLite 저장소를 반환합니다.
"""

from __future__ import annotations

from typing import Optional

from src.config import get_config

from .interfaces import Repository
from .csv_repository import CSVRepository, CsvRepoConfig
from .sqlite_repository import SqliteRepository, SqliteRepoConfig, SqliteDatabase


# SQLite 데이터베이스 싱글톤
_sqlite_db: Optional[SqliteDatabase] = None


def get_sqlite_db() -> SqliteDatabase:
    """SQLite 데이터베이스 싱글톤 반환."""
    global _sqlite_db
    if _sqlite_db is None:
        config = get_config()
        _sqlite_db = SqliteDatabase(config.paths.sqlite_path)
    return _sqlite_db


def get_repository(
    table_name: str,
    key_field: str,
    csv_filename: Optional[str] = None,
    json_fields: Optional[list] = None,
) -> Repository:
    """설정에 따라 적절한 저장소 반환.

    Args:
        table_name: 테이블/파일 이름 (SQLite용)
        key_field: 기본 키 필드
        csv_filename: CSV 파일명 (CSV 백엔드용, 없으면 table_name.csv 사용)
        json_fields: JSON 직렬화가 필요한 필드 목록

    Returns:
        설정된 백엔드의 Repository 구현체
    """
    config = get_config()
    backend = config.paths.storage_backend

    if backend == "sqlite":
        return SqliteRepository(SqliteRepoConfig(
            db_path=config.paths.sqlite_path,
            table_name=table_name,
            key_field=key_field,
            json_fields=json_fields,
        ))
    else:  # csv (기본값)
        filename = csv_filename or f"{table_name}.csv"
        return CSVRepository(CsvRepoConfig(
            data_dir=config.paths.data_dir,
            filename=filename,
            key_field=key_field,
            json_fields=json_fields,
        ))


# 편의 함수들
def get_users_repository() -> Repository:
    """사용자 저장소."""
    return get_repository("users", "user_id")


def get_orders_repository() -> Repository:
    """주문 저장소."""
    return get_repository("orders", "order_id")


def get_order_items_repository() -> Repository:
    """주문 아이템 저장소."""
    return get_repository("order_items", "id")


def get_products_repository() -> Repository:
    """상품 저장소."""
    return get_repository("products_cache", "product_id")


def get_tickets_repository() -> Repository:
    """티켓 저장소."""
    return get_repository("support_tickets", "ticket_id")


def get_cart_repository() -> Repository:
    """장바구니 저장소."""
    return get_repository("cart", "id")


def get_wishlist_repository() -> Repository:
    """위시리스트 저장소."""
    return get_repository("wishlist", "id")


def get_conversations_repository() -> Repository:
    """대화 저장소."""
    return get_repository("conversations", "id", json_fields=["messages"])
