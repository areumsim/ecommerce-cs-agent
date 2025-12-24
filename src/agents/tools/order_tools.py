from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.mock_system.order_service import InventoryService, OrderService
from src.mock_system.ticket_service import TicketService


_order_service: Optional[OrderService] = None
_inventory_service: Optional[InventoryService] = None
_ticket_service: Optional[TicketService] = None


def _orders() -> OrderService:
    global _order_service
    if _order_service is None:
        _order_service = OrderService()
    return _order_service


def _inventory() -> InventoryService:
    global _inventory_service
    if _inventory_service is None:
        _inventory_service = InventoryService()
    return _inventory_service


def _tickets() -> TicketService:
    global _ticket_service
    if _ticket_service is None:
        _ticket_service = TicketService()
    return _ticket_service


# -------- Order Tools (async) --------

async def get_user_orders(user_id: str, status: Optional[str] = None, limit: int = 10) -> List[Any]:
    return await _orders().get_user_orders(user_id=user_id, status=status, limit=limit)


async def get_order_detail(order_id: str) -> Any:
    return await _orders().get_order_detail(order_id)


async def get_order_status(order_id: str) -> Any:
    return await _orders().get_order_status(order_id)


async def request_cancel(order_id: str, reason: str) -> Dict[str, Any]:
    return await _orders().request_cancel(order_id, reason)


# -------- Ticket Tools (async) --------

async def create_ticket(user_id: str, order_id: Optional[str], issue_type: str, description: str, priority: str = "normal") -> Dict[str, Any]:
    return await _tickets().create_ticket(user_id=user_id, order_id=order_id, issue_type=issue_type, description=description, priority=priority)


async def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    return await _tickets().get_ticket(ticket_id)


async def list_user_tickets(user_id: str, status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    return await _tickets().list_user_tickets(user_id=user_id, status=status, limit=limit)


async def update_ticket_status(ticket_id: str, status: str) -> Dict[str, Any]:
    return await _tickets().update_ticket_status(ticket_id, status)


# -------- Inventory Tools (async) --------

async def check_stock(product_id: str) -> Dict[str, Any]:
    return await _inventory().check_stock(product_id)


async def reserve_stock(product_id: str, quantity: int) -> bool:
    return await _inventory().reserve_stock(product_id, quantity)

