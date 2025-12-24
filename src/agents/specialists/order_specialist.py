"""주문 전문 에이전트.

주문 조회, 상태 확인, 취소 등 주문 관련 요청을 처리합니다.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import AgentContext, AgentResponse, BaseAgent
from src.mock_system.order_service import OrderService


class OrderSpecialist(BaseAgent):
    """주문 전문 에이전트."""

    name = "order_specialist"
    description = "주문 조회, 상태 확인, 취소 등 주문 관련 업무를 담당합니다."
    supported_intents = ["order"]

    def __init__(self):
        super().__init__()
        self.order_service = OrderService()

    async def handle(self, context: AgentContext) -> AgentResponse:
        """주문 관련 요청 처리."""
        sub_intent = context.sub_intent or "list"
        entities = context.entities

        try:
            if sub_intent == "list":
                return await self._handle_list(context)
            elif sub_intent == "status":
                return await self._handle_status(context, entities.get("order_id", ""))
            elif sub_intent == "detail":
                return await self._handle_detail(context, entities.get("order_id", ""))
            elif sub_intent == "cancel":
                return await self._handle_cancel(context, entities.get("order_id", ""))
            else:
                return await self._handle_list(context)
        except Exception as e:
            self.logger.error(f"주문 처리 오류: {e}")
            return self._create_error_response(f"주문 처리 중 오류가 발생했습니다: {str(e)}")

    async def _handle_list(self, context: AgentContext) -> AgentResponse:
        """주문 목록 조회."""
        orders = await self.order_service.get_user_orders(context.user_id)

        if not orders:
            return AgentResponse(
                success=True,
                message="등록된 주문 내역이 없습니다.",
                data={"orders": []},
            )

        orders_data = [
            {
                "order_id": o.order_id,
                "status": o.status,
                "order_date": o.order_date,
                "total_amount": o.total_amount,
                "delivery_date": o.delivery_date,
            }
            for o in orders
        ]

        response_text = await self.generate_response_text(
            context,
            {"orders": orders_data},
        )

        return AgentResponse(
            success=True,
            message=response_text,
            data={"orders": orders_data},
            suggested_actions=self._get_order_actions(orders),
        )

    async def _handle_status(self, context: AgentContext, order_id: str) -> AgentResponse:
        """주문 상태 조회."""
        if not order_id:
            # 가장 최근 주문 조회
            orders = await self.order_service.get_user_orders(context.user_id, limit=1)
            if not orders:
                return AgentResponse(
                    success=True,
                    message="조회할 주문이 없습니다.",
                    data={},
                )
            order_id = orders[0].order_id

        try:
            status = await self.order_service.get_order_status(order_id)
            status_data = {
                "order_id": status.order_id,
                "status": status.status,
                "estimated_delivery": status.estimated_delivery,
            }

            response_text = await self.generate_response_text(
                context,
                {"status": status_data},
            )

            return AgentResponse(
                success=True,
                message=response_text,
                data={"status": status_data},
            )
        except KeyError:
            return self._create_error_response(f"주문번호 {order_id}를 찾을 수 없습니다.")

    async def _handle_detail(self, context: AgentContext, order_id: str) -> AgentResponse:
        """주문 상세 조회."""
        if not order_id:
            orders = await self.order_service.get_user_orders(context.user_id, limit=1)
            if not orders:
                return AgentResponse(
                    success=True,
                    message="조회할 주문이 없습니다.",
                    data={},
                )
            order_id = orders[0].order_id

        try:
            detail = await self.order_service.get_order_detail(order_id)
            detail_data = {
                "order": {
                    "order_id": detail.order.order_id,
                    "status": detail.order.status,
                    "order_date": detail.order.order_date,
                    "total_amount": detail.order.total_amount,
                    "shipping_address": detail.order.shipping_address,
                },
                "items": detail.items,
            }

            response_text = await self.generate_response_text(
                context,
                {"detail": detail_data},
            )

            return AgentResponse(
                success=True,
                message=response_text,
                data={"detail": detail_data},
            )
        except KeyError:
            return self._create_error_response(f"주문번호 {order_id}를 찾을 수 없습니다.")

    async def _handle_cancel(self, context: AgentContext, order_id: str) -> AgentResponse:
        """주문 취소 요청."""
        if not order_id:
            return AgentResponse(
                success=False,
                message="취소할 주문번호를 알려주세요.",
                data={},
                suggested_actions=["주문 목록 보기"],
            )

        try:
            reason = context.entities.get("reason", "고객 요청")
            result = await self.order_service.request_cancel(order_id, reason)

            if result.get("ok"):
                response_text = f"주문번호 {order_id}의 취소가 완료되었습니다."
                return AgentResponse(
                    success=True,
                    message=response_text,
                    data={"cancel_result": result},
                )
            else:
                error = result.get("error", "취소할 수 없는 상태입니다.")
                return AgentResponse(
                    success=False,
                    message=f"주문 취소에 실패했습니다. {error}",
                    data={"cancel_result": result},
                )
        except KeyError:
            return self._create_error_response(f"주문번호 {order_id}를 찾을 수 없습니다.")

    def _get_order_actions(self, orders: List) -> List[str]:
        """주문 목록에 따른 추천 액션 생성."""
        actions = []
        for order in orders[:3]:
            if order.status in ("pending", "confirmed"):
                actions.append(f"{order.order_id} 취소하기")
            elif order.status == "shipping":
                actions.append(f"{order.order_id} 배송 조회")
        return actions[:3]
