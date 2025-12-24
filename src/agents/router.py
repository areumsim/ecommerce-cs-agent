"""라우터 에이전트.

사용자 메시지를 분석하여 적절한 전문 에이전트에게 라우팅합니다.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from .specialists import (
    AgentContext,
    AgentResponse,
    BaseAgent,
    OrderSpecialist,
    ClaimSpecialist,
    PolicySpecialist,
    ProductSpecialist,
)
from .nodes.intent_classifier import classify_intent
from src.guardrails.pipeline import process_input, apply_guards


logger = logging.getLogger(__name__)


class AgentRouter:
    """에이전트 라우터.

    의도 분류 결과에 따라 적절한 전문 에이전트를 선택하고 실행합니다.
    """

    def __init__(self):
        # 전문 에이전트 등록
        self._agents: Dict[str, BaseAgent] = {}
        self._register_agents()

    def _register_agents(self) -> None:
        """전문 에이전트 등록."""
        agents: List[Type[BaseAgent]] = [
            OrderSpecialist,
            ClaimSpecialist,
            PolicySpecialist,
            ProductSpecialist,
        ]

        for agent_cls in agents:
            agent = agent_cls()
            for intent in agent.supported_intents:
                self._agents[intent] = agent
            logger.info(f"에이전트 등록: {agent.name} ({agent.supported_intents})")

    def get_agent(self, intent: str) -> Optional[BaseAgent]:
        """의도에 맞는 에이전트 반환."""
        return self._agents.get(intent)

    def list_agents(self) -> List[Dict[str, str]]:
        """등록된 에이전트 목록."""
        seen = set()
        result = []
        for agent in self._agents.values():
            if agent.name not in seen:
                seen.add(agent.name)
                result.append({
                    "name": agent.name,
                    "description": agent.description,
                    "intents": agent.supported_intents,
                })
        return result

    async def route(
        self,
        user_id: str,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AgentResponse:
        """메시지를 분석하고 적절한 에이전트에게 라우팅.

        Args:
            user_id: 사용자 ID
            message: 사용자 메시지
            history: 대화 히스토리 (선택)

        Returns:
            에이전트 응답
        """
        # 1. 입력 가드레일 적용
        input_result = process_input(message, strict_mode=False)
        if input_result.blocked:
            return AgentResponse(
                success=False,
                message=input_result.block_reason or "입력이 차단되었습니다.",
                data={"blocked": True},
            )

        # 2. 의도 분류
        intent, sub_intent, payload = classify_intent(message)
        logger.info(f"의도 분류: {intent}/{sub_intent}")

        # 3. 에이전트 선택
        agent = self.get_agent(intent)
        if agent is None:
            # 기본 정책 에이전트로 폴백
            agent = self._agents.get("policy") or self._agents.get("general")
            if agent is None:
                return AgentResponse(
                    success=False,
                    message="죄송합니다. 요청을 처리할 수 없습니다.",
                    data={"error": f"Unknown intent: {intent}"},
                )

        logger.info(f"에이전트 선택: {agent.name}")

        # 4. 컨텍스트 생성
        context = AgentContext(
            user_id=user_id,
            message=message,
            intent=intent,
            sub_intent=sub_intent,
            entities=payload,
            history=history or [],
        )

        # 5. 에이전트 실행
        try:
            response = await agent.handle(context)
        except Exception as e:
            logger.error(f"에이전트 실행 오류 ({agent.name}): {e}")
            return AgentResponse(
                success=False,
                message="죄송합니다. 요청 처리 중 오류가 발생했습니다.",
                data={"error": str(e)},
            )

        # 6. 출력 가드레일 적용
        guarded_data = apply_guards({
            "response": response.message,
            "data": response.data,
        })

        # 가드레일 적용된 응답으로 업데이트
        if isinstance(guarded_data, dict) and "response" in guarded_data:
            response.message = guarded_data["response"]
            response.data["guard"] = guarded_data.get("guard", {})

        return response


# 전역 라우터 인스턴스
_router: Optional[AgentRouter] = None


def get_router() -> AgentRouter:
    """전역 라우터 인스턴스 반환."""
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router


def reset_router() -> None:
    """라우터 리셋 (테스트용)."""
    global _router
    _router = None


async def process_message(
    user_id: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict:
    """사용자 메시지 처리 (API용 편의 함수).

    Args:
        user_id: 사용자 ID
        message: 사용자 메시지
        history: 대화 히스토리

    Returns:
        응답 딕셔너리
    """
    router = get_router()
    response = await router.route(user_id, message, history)

    return {
        "success": response.success,
        "response": response.message,
        "data": response.data,
        "suggested_actions": response.suggested_actions,
        "requires_escalation": response.requires_escalation,
    }
