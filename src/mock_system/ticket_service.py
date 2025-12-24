from __future__ import annotations
"""CSV 기반 티켓(클레임/문의) Mock 서비스.

설계 요약
- 저장소: `csv_repository.CSVRepository`로 `support_tickets.csv`를 관리합니다.
- 상태 전이: open → (in_progress) → resolved (간단 구현에서는 open/resolved만 사용)
- 생성 시 `TICKET-<epoch>` 규칙으로 식별자를 발급합니다.

주의
- 단일-라이터 사용을 권장합니다.
- 날짜는 ISO8601 문자열을 권장합니다.
"""

import datetime as dt
from typing import Any, Dict, List, Optional

from .storage.factory import get_tickets_repository
from .storage.interfaces import Repository


class TicketService:
    """문의/클레임 티켓 Mock 서비스."""

    def __init__(self) -> None:
        self.tickets: Repository = get_tickets_repository()

    async def create_ticket(
        self,
        user_id: str,
        order_id: Optional[str],
        issue_type: str,
        description: str,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        ticket_id = f"TICKET-{int(dt.datetime.utcnow().timestamp())}"
        rec = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "order_id": order_id or "",
            "issue_type": issue_type,
            "description": description,
            "status": "open",
            "priority": priority,
            "created_at": now,
            "resolved_at": "",
        }
        self.tickets.create(rec)
        return rec

    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        return self.tickets.get_by_id(ticket_id)

    async def list_user_tickets(self, user_id: str, status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.tickets.query({"user_id": user_id})
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows[: max(0, limit)]

    async def update_ticket_status(self, ticket_id: str, status: str) -> Dict[str, Any]:
        patch = {"status": status}
        if status == "resolved":
            patch["resolved_at"] = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        updated = self.tickets.update(ticket_id, patch)
        return updated
