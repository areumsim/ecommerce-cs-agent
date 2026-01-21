from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from src.agents.tools import order_tools


def _serialize_order_item(item: Any) -> Dict[str, Any]:
    """OrderItem 객체를 직렬화 가능한 dict로 변환."""
    if hasattr(item, '__dict__'):
        # dataclass 또는 일반 객체
        d = item.__dict__.copy() if hasattr(item, '__dict__') else {}
        # datetime 필드 처리
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        return d
    if isinstance(item, dict):
        return item
    return {"value": str(item)}


async def handle_order_query(user_id: str, sub_intent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """sub_intent: list/status/detail/cancel"""
    if sub_intent == "list":
        orders = await order_tools.get_user_orders(user_id, payload.get("status"), int(payload.get("limit", 10)))
        return {"orders": [o.__dict__ for o in orders]}
    if sub_intent == "status":
        st = await order_tools.get_order_status(payload["order_id"])  # type: ignore[index]
        return {"status": st.__dict__}
    if sub_intent == "detail":
        detail = await order_tools.get_order_detail(payload["order_id"])  # type: ignore[index]
        # OrderItem 객체들을 dict로 변환 (JSON 직렬화 가능하도록)
        items_serialized = [_serialize_order_item(item) for item in detail.items]
        return {"detail": {"order": detail.order.__dict__, "items": items_serialized}}
    if sub_intent == "cancel":
        res = await order_tools.request_cancel(payload["order_id"], payload.get("reason", ""))  # type: ignore[index]
        return {"cancel_result": res}
    return {"error": f"unknown sub_intent: {sub_intent}"}

