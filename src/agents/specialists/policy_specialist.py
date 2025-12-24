"""정책 전문 에이전트.

환불, 배송, 교환 정책 등 FAQ 질문을 처리합니다.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import AgentContext, AgentResponse, BaseAgent
from src.rag.retriever import PolicyRetriever


class PolicySpecialist(BaseAgent):
    """정책 전문 에이전트."""

    name = "policy_specialist"
    description = "환불, 배송, 교환 정책 등 FAQ 질문을 담당합니다."
    supported_intents = ["policy", "faq", "general"]

    def __init__(self):
        super().__init__()
        self.retriever = PolicyRetriever()

    async def handle(self, context: AgentContext) -> AgentResponse:
        """정책 질문 처리."""
        query = context.message

        try:
            # RAG 검색
            hits = self.retriever.search_policy(query, top_k=3)

            if not hits:
                return await self._handle_no_results(context)

            # 검색 결과 포맷
            hits_data = [
                {
                    "id": h.id,
                    "score": h.score,
                    "text": h.text,
                    "doc_type": h.metadata.get("doc_type", ""),
                }
                for h in hits
            ]

            # LLM으로 응답 생성
            response_text = await self._generate_policy_response(context, hits_data)

            suggested_actions = self._get_related_topics(hits_data)

            return AgentResponse(
                success=True,
                message=response_text,
                data={"hits": hits_data, "query": query},
                suggested_actions=suggested_actions,
            )

        except Exception as e:
            self.logger.error(f"정책 검색 오류: {e}")
            return self._create_error_response(f"정책 검색 중 오류가 발생했습니다: {str(e)}")

    async def _handle_no_results(self, context: AgentContext) -> AgentResponse:
        """검색 결과 없음 처리."""
        message = (
            "죄송합니다. 관련 정책 정보를 찾지 못했습니다.\n"
            "다른 키워드로 검색하시거나, 고객센터에 문의해 주세요."
        )

        return AgentResponse(
            success=True,
            message=message,
            data={"hits": [], "query": context.message},
            suggested_actions=[
                "환불 정책 보기",
                "배송 정책 보기",
                "교환 정책 보기",
                "고객센터 연결",
            ],
        )

    async def _generate_policy_response(
        self,
        context: AgentContext,
        hits: List[Dict[str, Any]],
    ) -> str:
        """정책 응답 생성."""
        # 최고 점수 문서 사용
        best_hit = hits[0]
        score = best_hit.get("score", 0)

        # 높은 신뢰도
        if score >= 0.8:
            response = await self.generate_response_text(
                context,
                {"hits": hits},
            )
            return response

        # 중간 신뢰도
        if score >= 0.5:
            response = await self.generate_response_text(
                context,
                {"hits": hits},
            )
            disclaimer = "\n\n※ 더 자세한 내용은 고객센터에 문의해 주세요."
            return response + disclaimer

        # 낮은 신뢰도
        return self._format_low_confidence_response(hits)

    def _format_low_confidence_response(self, hits: List[Dict[str, Any]]) -> str:
        """낮은 신뢰도 응답 포맷."""
        response = "관련될 수 있는 정책을 찾았습니다:\n\n"

        for i, hit in enumerate(hits[:2], 1):
            text = hit.get("text", "")[:200]
            response += f"{i}. {text}...\n\n"

        response += "정확한 정보가 필요하시면 고객센터에 문의해 주세요."
        return response

    def _get_related_topics(self, hits: List[Dict[str, Any]]) -> List[str]:
        """관련 주제 추천."""
        doc_types = set()
        for hit in hits:
            doc_type = hit.get("doc_type", "")
            if doc_type:
                doc_types.add(doc_type)

        actions = []
        type_to_action = {
            "refund": "환불 정책 더 보기",
            "shipping": "배송 정책 더 보기",
            "exchange": "교환 정책 더 보기",
            "faq": "자주 묻는 질문",
            "defect": "불량품 처리 안내",
        }

        for doc_type in doc_types:
            if doc_type in type_to_action:
                actions.append(type_to_action[doc_type])

        # 관련 없는 주제도 추천
        all_actions = list(type_to_action.values())
        for action in all_actions:
            if action not in actions and len(actions) < 3:
                actions.append(action)

        return actions[:3]
