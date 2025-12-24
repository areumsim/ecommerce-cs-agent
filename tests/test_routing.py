"""LLM 라우팅 경로 검증 테스트.

의도별로 generate_routed_response가 호출되어 응답이 반영되는지 확인한다.
실제 네트워크 호출은 하지 않도록 monkeypatch로 차단한다.
"""

import pytest

from src.agents.state import AgentState
from src.agents import orchestrator


@pytest.fixture(autouse=True)
def force_local_provider(monkeypatch):
    """LLM 사용 가능하도록 provider를 local로 강제.

    orchestrator._is_llm_available()가 True가 되도록 환경변수를 주입한다.
    """
    monkeypatch.setenv("LLM_PROVIDER", "local")


@pytest.mark.asyncio
async def test_routed_policy_intent(monkeypatch):
    async def fake_routed_response(context, user_message, intent):
        assert intent == "policy"
        return "ROUTED_LOCAL_POLICY"

    monkeypatch.setattr(orchestrator, "generate_routed_response", fake_routed_response, raising=True)

    state = AgentState(user_id="u1", intent="policy", sub_intent=None, payload={"query": "환불", "top_k": 3})
    out = await orchestrator.run(state)
    assert out.final_response is not None
    # 라우팅된 응답이 response 필드로 반영되어야 한다
    assert out.final_response.get("response") == "ROUTED_LOCAL_POLICY"


@pytest.mark.asyncio
async def test_routed_order_intent(monkeypatch):
    async def fake_routed_response(context, user_message, intent):
        assert intent == "order"
        return "ROUTED_LOCAL_ORDER"

    monkeypatch.setattr(orchestrator, "generate_routed_response", fake_routed_response, raising=True)

    state = AgentState(user_id="user_001", intent="order", sub_intent="list", payload={"limit": 1})
    out = await orchestrator.run(state)
    assert out.final_response is not None
    assert out.final_response.get("response") == "ROUTED_LOCAL_ORDER"


@pytest.mark.asyncio
async def test_routed_claim_intent(monkeypatch):
    async def fake_routed_response(context, user_message, intent):
        assert intent == "claim"
        return "ROUTED_LOCAL_CLAIM"

    monkeypatch.setattr(orchestrator, "generate_routed_response", fake_routed_response, raising=True)

    state = AgentState(user_id="user_001", intent="claim", sub_intent=None, payload={"action": "create", "issue_type": "refund", "description": "불량"})
    out = await orchestrator.run(state)
    assert out.final_response is not None
    assert out.final_response.get("response") == "ROUTED_LOCAL_CLAIM"
