"""클레임 전문 에이전트.

환불, 교환, 불량품 처리 등 클레임 관련 요청을 처리합니다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from .base import AgentContext, AgentResponse, BaseAgent
from src.mock_system.ticket_service import TicketService
from src.mock_system.order_service import OrderService


class ClaimSpecialist(BaseAgent):
    """클레임 전문 에이전트."""

    name = "claim_specialist"
    description = "환불, 교환, 불량품 처리 등 클레임 업무를 담당합니다."
    supported_intents = ["claim"]

    # 클레임 유형 매핑
    CLAIM_TYPE_MAP = {
        "환불": "refund",
        "반품": "refund",
        "교환": "exchange",
        "불량": "defect",
        "파손": "defect",
        "고장": "defect",
    }

    def __init__(self, use_vision: bool = True):
        super().__init__()
        self.ticket_service = TicketService()
        self.order_service = OrderService()
        self.use_vision = use_vision
        self._defect_detector = None

    def _get_defect_detector(self):
        """불량 탐지기 지연 로딩."""
        if self._defect_detector is None and self.use_vision:
            try:
                from src.vision import get_defect_detector
                self._defect_detector = get_defect_detector(use_clip=False)
            except Exception as e:
                self.logger.warning(f"비전 모듈 로드 실패: {e}")
                self._defect_detector = None
        return self._defect_detector

    async def handle(self, context: AgentContext) -> AgentResponse:
        """클레임 요청 처리."""
        entities = context.entities
        claim_type = self._detect_claim_type(context.message)

        try:
            # 주문 ID가 있으면 주문 확인
            order_id = entities.get("order_id", "")
            if order_id:
                order_valid = await self._validate_order(context.user_id, order_id)
                if not order_valid:
                    return self._create_error_response(
                        f"주문번호 {order_id}를 찾을 수 없거나 접근 권한이 없습니다."
                    )

            # 이미지가 있으면 불량 분석
            image_analysis = None
            image_data = entities.get("image") or entities.get("image_path")
            if image_data and claim_type == "defect":
                image_analysis = await self.analyze_defect_image(image_data)
                if image_analysis:
                    entities["image_analysis"] = image_analysis

            # 티켓 생성
            return await self._create_claim_ticket(context, claim_type, order_id, image_analysis)

        except Exception as e:
            self.logger.error(f"클레임 처리 오류: {e}")
            return self._create_error_response(f"클레임 처리 중 오류가 발생했습니다: {str(e)}")

    async def analyze_defect_image(
        self,
        image: Union[str, Path, bytes],
    ) -> Optional[Dict[str, Any]]:
        """불량품 이미지 분석.

        Args:
            image: 이미지 경로, bytes, 또는 base64 문자열

        Returns:
            분석 결과 딕셔너리 또는 None
        """
        detector = self._get_defect_detector()
        if detector is None:
            return None

        try:
            result = await detector.analyze(image)
            if result.success:
                return {
                    "defect_type": result.attributes.get("defect_type", "알 수 없음"),
                    "is_defective": result.attributes.get("is_defective", False),
                    "confidence": result.confidence,
                    "description": result.description,
                    "labels": result.labels,
                }
            return None
        except Exception as e:
            self.logger.warning(f"이미지 분석 실패: {e}")
            return None

    async def _validate_order(self, user_id: str, order_id: str) -> bool:
        """주문 유효성 검증."""
        try:
            detail = await self.order_service.get_order_detail(order_id)
            return detail.order.user_id == user_id
        except KeyError:
            return False

    async def _create_claim_ticket(
        self,
        context: AgentContext,
        claim_type: str,
        order_id: str,
        image_analysis: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """클레임 티켓 생성."""
        description = context.entities.get("description", context.message)

        # 이미지 분석 결과가 있으면 설명에 추가
        if image_analysis:
            description += f"\n\n[이미지 분석 결과]\n{image_analysis.get('description', '')}"

        # 우선순위 결정
        priority = self._determine_priority(claim_type, context.message)

        # 이미지 분석에서 불량이 확인되면 우선순위 상향
        if image_analysis and image_analysis.get("is_defective"):
            priority = "high"

        ticket = await self.ticket_service.create_ticket(
            user_id=context.user_id,
            order_id=order_id,
            issue_type=claim_type,
            description=description,
            priority=priority,
        )

        ticket_data = {
            "ticket_id": ticket.get("ticket_id"),
            "issue_type": ticket.get("issue_type"),
            "status": ticket.get("status"),
            "priority": ticket.get("priority"),
            "order_id": order_id,
        }

        # 이미지 분석 결과 포함
        if image_analysis:
            ticket_data["image_analysis"] = image_analysis

        response_text = await self._generate_claim_response(context, ticket_data, image_analysis)

        suggested_actions = self._get_claim_actions(claim_type)

        return AgentResponse(
            success=True,
            message=response_text,
            data={"ticket": ticket_data},
            suggested_actions=suggested_actions,
        )

    def _detect_claim_type(self, message: str) -> str:
        """메시지에서 클레임 유형 감지."""
        for keyword, claim_type in self.CLAIM_TYPE_MAP.items():
            if keyword in message:
                return claim_type
        return "inquiry"  # 기본값

    def _determine_priority(self, claim_type: str, message: str) -> str:
        """우선순위 결정."""
        high_priority_keywords = ["긴급", "급함", "빨리", "당장", "즉시"]
        if any(kw in message for kw in high_priority_keywords):
            return "high"

        if claim_type in ("defect", "refund"):
            return "normal"

        return "low"

    async def _generate_claim_response(
        self,
        context: AgentContext,
        ticket_data: Dict[str, Any],
        image_analysis: Optional[Dict[str, Any]] = None,
    ) -> str:
        """클레임 응답 생성."""
        claim_type = ticket_data.get("issue_type", "")
        ticket_id = ticket_data.get("ticket_id", "")

        type_messages = {
            "refund": "환불 요청",
            "exchange": "교환 요청",
            "defect": "불량품 신고",
            "inquiry": "문의",
        }

        type_name = type_messages.get(claim_type, "요청")

        response = f"{type_name}이 접수되었습니다.\n"
        response += f"티켓번호: {ticket_id}\n\n"

        # 이미지 분석 결과가 있으면 포함
        if image_analysis:
            response += "[이미지 분석 결과]\n"
            if image_analysis.get("is_defective"):
                response += f"- 불량 유형: {image_analysis.get('defect_type', '알 수 없음')}\n"
                response += f"- 신뢰도: {image_analysis.get('confidence', 0) * 100:.1f}%\n"
                response += "- 자동 분석 결과 불량이 확인되어 우선 처리됩니다.\n\n"
            else:
                response += "- 이미지 분석 결과 명확한 불량이 감지되지 않았습니다.\n"
                response += "- 담당자가 직접 확인 후 처리해 드리겠습니다.\n\n"

        if claim_type == "refund":
            response += "환불 처리는 검토 후 3-5 영업일 내에 완료됩니다."
        elif claim_type == "exchange":
            response += "교환 상품은 검수 완료 후 발송됩니다."
        elif claim_type == "defect":
            if not image_analysis:
                response += "불량 확인을 위해 상품 사진을 첨부해 주시면 더 빠른 처리가 가능합니다.\n"
            response += "불량 확인 후 교환 또는 환불 처리해 드리겠습니다."
        else:
            response += "담당자가 확인 후 연락드리겠습니다."

        return response

    def _get_claim_actions(self, claim_type: str) -> List[str]:
        """클레임 유형별 추천 액션."""
        actions = ["티켓 상태 확인"]

        if claim_type == "refund":
            actions.extend(["환불 정책 확인", "주문 내역 보기"])
        elif claim_type == "exchange":
            actions.extend(["교환 정책 확인", "재고 확인"])
        elif claim_type == "defect":
            actions.extend(["불량품 처리 안내", "사진 첨부하기"])

        return actions
