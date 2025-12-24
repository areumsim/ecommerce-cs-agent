from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AgentState:
    user_id: str
    intent: str  # order|claim|policy
    sub_intent: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    final_response: Optional[Dict[str, Any]] = None

