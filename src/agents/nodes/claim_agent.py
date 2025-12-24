from __future__ import annotations

from typing import Any, Dict

from src.agents.tools import order_tools


async def handle_claim(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    action = payload.get("action", "create")
    if action == "create":
        rec = await order_tools.create_ticket(
            user_id=user_id,
            order_id=payload.get("order_id"),
            issue_type=payload.get("issue_type", "other"),
            description=payload.get("description", ""),
            priority=payload.get("priority", "normal"),
        )
        return {"ticket": rec}
    if action == "status":
        t = await order_tools.get_ticket(payload["ticket_id"])  # type: ignore[index]
        return {"ticket": t}
    if action == "resolve":
        updated = await order_tools.update_ticket_status(payload["ticket_id"], "resolved")  # type: ignore[index]
        return {"ticket": updated}
    return {"error": f"unknown action: {action}"}

