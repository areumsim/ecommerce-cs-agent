from __future__ import annotations

from typing import Any, Dict

from src.agents.tools import order_tools


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
        return {"detail": {"order": detail.order.__dict__, "items": detail.items}}
    if sub_intent == "cancel":
        res = await order_tools.request_cancel(payload["order_id"], payload.get("reason", ""))  # type: ignore[index]
        return {"cancel_result": res}
    return {"error": f"unknown sub_intent: {sub_intent}"}

