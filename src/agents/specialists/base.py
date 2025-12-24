"""기본 에이전트 클래스.

모든 전문 에이전트가 상속받는 베이스 클래스입니다.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.llm.client import generate_response


logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """에이전트 컨텍스트."""

    user_id: str
    message: str
    intent: str = ""
    sub_intent: str = ""
    entities: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """에이전트 응답."""

    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
    requires_escalation: bool = False
    escalation_reason: str = ""


class BaseAgent(ABC):
    """기본 에이전트 클래스.

    모든 전문 에이전트는 이 클래스를 상속받아 구현합니다.
    """

    name: str = "base"
    description: str = "기본 에이전트"
    supported_intents: List[str] = []

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    async def handle(self, context: AgentContext) -> AgentResponse:
        """요청을 처리합니다.

        Args:
            context: 에이전트 컨텍스트

        Returns:
            에이전트 응답
        """
        pass

    def can_handle(self, intent: str) -> bool:
        """이 에이전트가 해당 의도를 처리할 수 있는지 확인.

        Args:
            intent: 의도

        Returns:
            처리 가능 여부
        """
        return intent in self.supported_intents

    async def generate_response_text(
        self,
        context: AgentContext,
        data: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> str:
        """LLM을 사용하여 응답 텍스트 생성.

        Args:
            context: 에이전트 컨텍스트
            data: 응답에 포함할 데이터
            system_prompt: 시스템 프롬프트 (선택)

        Returns:
            생성된 응답 텍스트
        """
        try:
            response = await generate_response(
                context=data,
                user_message=context.message,
                intent=context.intent,
            )
            return response
        except Exception as e:
            self.logger.warning(f"LLM 응답 생성 실패: {e}")
            return self._format_fallback_response(data)

    def _format_fallback_response(self, data: Dict[str, Any]) -> str:
        """LLM 실패 시 기본 응답 포맷.

        Args:
            data: 응답 데이터

        Returns:
            포맷된 응답 문자열
        """
        if "error" in data:
            return f"죄송합니다. 오류가 발생했습니다: {data['error']}"
        return "요청을 처리했습니다."

    def _create_error_response(self, error: str) -> AgentResponse:
        """에러 응답 생성.

        Args:
            error: 에러 메시지

        Returns:
            에러 응답
        """
        return AgentResponse(
            success=False,
            message=f"죄송합니다. {error}",
            data={"error": error},
        )

    def _create_escalation_response(self, reason: str) -> AgentResponse:
        """에스컬레이션 응답 생성.

        Args:
            reason: 에스컬레이션 사유

        Returns:
            에스컬레이션 응답
        """
        return AgentResponse(
            success=True,
            message="담당자에게 연결해 드리겠습니다.",
            requires_escalation=True,
            escalation_reason=reason,
        )
