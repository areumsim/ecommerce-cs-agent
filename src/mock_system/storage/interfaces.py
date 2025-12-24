from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol


class Repository(Protocol):
    """Generic repository interface for CSV/SQL backends."""

    def get_by_id(self, _id: str) -> Optional[Dict[str, Any]]:
        ...

    def query(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        ...

    def create(self, record: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def update(self, _id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def delete(self, _id: str) -> None:
        ...


class UsersRepository(Repository, Protocol):
    pass


class OrdersRepository(Repository, Protocol):
    pass


class OrderItemsRepository(Repository, Protocol):
    pass


class CartRepository(Repository, Protocol):
    pass


class WishlistRepository(Repository, Protocol):
    pass


class TicketsRepository(Repository, Protocol):
    pass


class ConversationsRepository(Repository, Protocol):
    pass


class ProductsCacheRepository(Repository, Protocol):
    pass


@dataclass
class CsvRepoConfig:
    data_dir: str
    filename: str
    key_field: str
    json_fields: Optional[List[str]] = None

