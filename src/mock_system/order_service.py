from __future__ import annotations
"""CSV 기반 주문/재고 Mock 서비스.

설계 요약
- 저장소: `csv_repository.CSVRepository`를 사용해 `data/mock_csv/*.csv`를 로드/저장합니다.
- 주문 상태 전이: pending/confirmed/shipping/delivered/cancelled (취소는 배송 전 상태에서만 허용)
- 상세 조회: 주문 아이템과 제품 캐시를 조인하여 타이틀/브랜드/이미지 등의 정보를 포함합니다.

주의
- 단일-라이터 사용을 권장합니다(동시 쓰기 미지원).
- 날짜는 ISO8601 문자열을 권장합니다.
"""

import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .storage.factory import (
    get_orders_repository,
    get_order_items_repository,
    get_products_repository,
)
from .storage.interfaces import Repository


@dataclass
class Order:
    order_id: str
    user_id: str
    status: str
    order_date: str
    delivery_date: Optional[str]
    total_amount: str
    shipping_address: str


@dataclass
class OrderItem:
    id: str
    order_id: str
    product_id: str
    quantity: int
    unit_price: str


@dataclass
class OrderDetail:
    order: Order
    items: List[Dict[str, Any]]  # merged with product info


@dataclass
class OrderStatus:
    order_id: str
    status: str
    estimated_delivery: Optional[str]


class OrderService:
    """주문 관련 Mock 서비스."""

    def __init__(self) -> None:
        self.orders: Repository = get_orders_repository()
        self.items: Repository = get_order_items_repository()
        self.products: Repository = get_products_repository()

    async def get_user_orders(self, user_id: str, status: str | None = None, limit: int = 10) -> List[Order]:
        rows = self.orders.query({"user_id": user_id} if user_id else None)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows.sort(key=lambda r: r.get("order_date", ""), reverse=True)
        rows = rows[: max(0, limit)]
        return [Order(
            order_id=r.get("order_id", ""),
            user_id=r.get("user_id", ""),
            status=r.get("status", ""),
            order_date=r.get("order_date", ""),
            delivery_date=r.get("delivery_date"),
            total_amount=r.get("total_amount", "0"),
            shipping_address=r.get("shipping_address", ""),
        ) for r in rows]

    async def get_order_detail(self, order_id: str) -> OrderDetail:
        r = self.orders.get_by_id(order_id)
        if not r:
            raise KeyError(order_id)
        order = Order(
            order_id=r.get("order_id", ""),
            user_id=r.get("user_id", ""),
            status=r.get("status", ""),
            order_date=r.get("order_date", ""),
            delivery_date=r.get("delivery_date"),
            total_amount=r.get("total_amount", "0"),
            shipping_address=r.get("shipping_address", ""),
        )
        items = [it for it in self.items.query({"order_id": order_id})]
        merged: List[Dict[str, Any]] = []
        for it in items:
            prod = self.products.get_by_id(it.get("product_id", "")) or {}
            merged.append({
                **it,
                "title": prod.get("title"),
                "brand": prod.get("brand"),
                "price": prod.get("price"),
                "image_url": prod.get("image_url"),
            })
        return OrderDetail(order=order, items=merged)

    async def get_order_status(self, order_id: str) -> OrderStatus:
        r = self.orders.get_by_id(order_id)
        if not r:
            raise KeyError(order_id)
        status = r.get("status", "pending")
        est = r.get("delivery_date")
        if not est:
            try:
                od = dt.datetime.fromisoformat(r.get("order_date"))
                est = (od + dt.timedelta(days=3)).isoformat()
            except Exception:
                est = None
        return OrderStatus(order_id=order_id, status=status, estimated_delivery=est)

    async def request_cancel(self, order_id: str, reason: str) -> Dict[str, Any]:
        r = self.orders.get_by_id(order_id)
        if not r:
            raise KeyError(order_id)
        if r.get("status") in {"pending", "confirmed"}:
            updated = self.orders.update(order_id, {"status": "cancelled"})
            return {"ok": True, "order_id": order_id, "status": updated.get("status"), "reason": reason}
        return {"ok": False, "order_id": order_id, "status": r.get("status"), "error": "Cancellable only before shipping"}


class InventoryService:
    """재고 Mock 서비스."""

    def __init__(self) -> None:
        self.products: Repository = get_products_repository()

    async def check_stock(self, product_id: str) -> Dict[str, Any]:
        p = self.products.get_by_id(product_id)
        if not p:
            return {"product_id": product_id, "stock_quantity": 0, "exists": False}
        qty = int(str(p.get("stock_quantity") or 0))
        return {"product_id": product_id, "stock_quantity": qty, "exists": True}

    async def reserve_stock(self, product_id: str, quantity: int) -> bool:
        if quantity <= 0:
            return False
        p = self.products.get_by_id(product_id)
        if not p:
            return False
        qty = int(str(p.get("stock_quantity") or 0))
        if qty < quantity:
            return False
        self.products.update(product_id, {"stock_quantity": str(qty - quantity)})
        return True
