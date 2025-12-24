#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.agents.state import AgentState
from src.agents.orchestrator import run


async def main() -> None:
    user_id = "user_001"

    s1 = AgentState(user_id=user_id, intent="order", sub_intent="list", payload={"limit": 5})
    s1 = await run(s1)
    print("[orders]", s1.final_response)

    orders = (s1.final_response or {}).get("orders", [])
    order_id = orders[0]["order_id"] if orders else "ORD-user_001-1704825600"

    s2 = AgentState(user_id=user_id, intent="order", sub_intent="detail", payload={"order_id": order_id})
    s2 = await run(s2)
    print("[detail]", s2.final_response)

    s3 = AgentState(user_id=user_id, intent="order", sub_intent="status", payload={"order_id": order_id})
    s3 = await run(s3)
    print("[status]", s3.final_response)

    s4 = AgentState(user_id=user_id, intent="order", sub_intent="cancel", payload={"order_id": order_id, "reason": "변심"})
    s4 = await run(s4)
    print("[cancel]", s4.final_response)

    s5 = AgentState(user_id=user_id, intent="claim", payload={"action": "create", "order_id": order_id, "issue_type": "refund", "description": "불량 환불"})
    s5 = await run(s5)
    print("[ticket-create]", s5.final_response)

    ticket_id = (s5.final_response or {}).get("ticket", {}).get("ticket_id")
    if ticket_id:
        s6 = AgentState(user_id=user_id, intent="claim", payload={"action": "status", "ticket_id": ticket_id})
        s6 = await run(s6)
        print("[ticket-status]", s6.final_response)


if __name__ == "__main__":
    asyncio.run(main())
