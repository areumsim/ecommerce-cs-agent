from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.rdf.repository import (
    get_rdf_repository,
    RDFRepository,
    Order,
    OrderDetail,
    OrderStatus,
    OrderItem,
    Ticket,
)


def _repo() -> RDFRepository:
    return get_rdf_repository()


async def get_user_orders(user_id: str, status: Optional[str] = None, limit: int = 10) -> List[Order]:
    return _repo().get_user_orders(user_id=user_id, status=status, limit=limit)


async def get_order_detail(order_id: str) -> OrderDetail:
    detail = _repo().get_order_detail(order_id)
    if not detail:
        raise KeyError(order_id)
    return detail


async def get_order_status(order_id: str) -> OrderStatus:
    status = _repo().get_order_status(order_id)
    if not status:
        raise KeyError(order_id)
    return status


async def request_cancel(order_id: str, reason: str) -> Dict[str, Any]:
    order = _repo().get_order(order_id)
    if not order:
        raise KeyError(order_id)
    
    if order.status in {"pending", "confirmed"}:
        _repo().update_order_status(order_id, "cancelled")
        return {"ok": True, "order_id": order_id, "status": "cancelled", "reason": reason}
    return {"ok": False, "order_id": order_id, "status": order.status, "error": "Cancellable only before shipping"}


async def create_ticket(
    user_id: str, 
    order_id: Optional[str], 
    issue_type: str, 
    description: str, 
    priority: str = "normal"
) -> Dict[str, Any]:
    ticket = _repo().create_ticket(
        user_id=user_id,
        order_id=order_id,
        issue_type=issue_type,
        description=description,
        priority=priority,
    )
    return {
        "ticket_id": ticket.ticket_id,
        "user_id": ticket.user_id,
        "order_id": ticket.order_id,
        "issue_type": ticket.issue_type,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }


async def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    ticket = _repo().get_ticket(ticket_id)
    if not ticket:
        return None
    return {
        "ticket_id": ticket.ticket_id,
        "user_id": ticket.user_id,
        "order_id": ticket.order_id,
        "issue_type": ticket.issue_type,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }


async def list_user_tickets(user_id: str, status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    tickets = _repo().get_user_tickets(user_id=user_id, status=status, limit=limit)
    return [
        {
            "ticket_id": t.ticket_id,
            "user_id": t.user_id,
            "order_id": t.order_id,
            "issue_type": t.issue_type,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        }
        for t in tickets
    ]


async def update_ticket_status(ticket_id: str, status: str) -> Dict[str, Any]:
    _repo().update_ticket_status(ticket_id, status)
    ticket = _repo().get_ticket(ticket_id)
    if not ticket:
        return {"error": "Ticket not found"}
    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }


async def check_stock(product_id: str) -> Dict[str, Any]:
    product = _repo().get_product(product_id)
    if not product:
        return {"product_id": product_id, "stock_quantity": 0, "exists": False}
    stock_qty = 100 if product.stock_status == "in_stock" else 0
    return {"product_id": product_id, "stock_quantity": stock_qty, "exists": True}


async def reserve_stock(product_id: str, quantity: int) -> bool:
    if quantity <= 0:
        return False
    product = _repo().get_product(product_id)
    if not product:
        return False
    return product.stock_status == "in_stock"
