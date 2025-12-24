"""상품 전문 에이전트.

상품 정보 조회, 재고 확인 등 상품 관련 요청을 처리합니다.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import AgentContext, AgentResponse, BaseAgent
from src.mock_system.order_service import InventoryService
from src.mock_system.storage.factory import get_products_repository


class ProductSpecialist(BaseAgent):
    """상품 전문 에이전트."""

    name = "product_specialist"
    description = "상품 정보 조회, 재고 확인 등 상품 관련 업무를 담당합니다."
    supported_intents = ["product"]

    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.products_repo = get_products_repository()

    async def handle(self, context: AgentContext) -> AgentResponse:
        """상품 관련 요청 처리."""
        sub_intent = context.sub_intent or "info"
        entities = context.entities

        try:
            product_id = entities.get("product_id", "")

            if sub_intent == "stock":
                return await self._handle_stock(context, product_id)
            elif sub_intent == "info":
                return await self._handle_info(context, product_id)
            elif sub_intent == "search":
                return await self._handle_search(context)
            else:
                return await self._handle_info(context, product_id)

        except Exception as e:
            self.logger.error(f"상품 처리 오류: {e}")
            return self._create_error_response(f"상품 정보 조회 중 오류가 발생했습니다: {str(e)}")

    async def _handle_stock(self, context: AgentContext, product_id: str) -> AgentResponse:
        """재고 확인."""
        if not product_id:
            return AgentResponse(
                success=False,
                message="재고를 확인할 상품 ID를 알려주세요.",
                data={},
            )

        stock = await self.inventory_service.check_stock(product_id)

        if not stock.get("exists"):
            return self._create_error_response(f"상품 {product_id}를 찾을 수 없습니다.")

        qty = stock.get("stock_quantity", 0)

        if qty > 10:
            status = "충분"
            message = f"재고가 충분합니다. ({qty}개)"
        elif qty > 0:
            status = "품절임박"
            message = f"재고가 얼마 남지 않았습니다. ({qty}개)"
        else:
            status = "품절"
            message = "현재 품절입니다. 재입고 알림을 신청해 주세요."

        return AgentResponse(
            success=True,
            message=message,
            data={
                "product_id": product_id,
                "stock_quantity": qty,
                "stock_status": status,
            },
            suggested_actions=self._get_stock_actions(status),
        )

    async def _handle_info(self, context: AgentContext, product_id: str) -> AgentResponse:
        """상품 정보 조회."""
        if not product_id:
            # 상품 ID 없으면 검색으로 전환
            return await self._handle_search(context)

        product = self.products_repo.get_by_id(product_id)

        if not product:
            return self._create_error_response(f"상품 {product_id}를 찾을 수 없습니다.")

        product_data = {
            "product_id": product.get("product_id"),
            "title": product.get("title"),
            "brand": product.get("brand"),
            "category": product.get("category"),
            "price": product.get("price"),
            "avg_rating": product.get("avg_rating"),
            "stock_quantity": product.get("stock_quantity"),
        }

        response_text = self._format_product_info(product_data)

        return AgentResponse(
            success=True,
            message=response_text,
            data={"product": product_data},
            suggested_actions=["재고 확인", "리뷰 보기", "장바구니 담기"],
        )

    async def _handle_search(self, context: AgentContext) -> AgentResponse:
        """상품 검색."""
        query = context.message
        keywords = self._extract_keywords(query)

        if not keywords:
            return AgentResponse(
                success=True,
                message="어떤 상품을 찾으시나요? 상품명이나 카테고리를 알려주세요.",
                data={},
                suggested_actions=["인기 상품 보기", "카테고리 보기"],
            )

        # 간단한 키워드 검색 (실제로는 더 정교한 검색 필요)
        all_products = self.products_repo.query(None)
        matches = []

        for product in all_products[:1000]:  # 성능상 제한
            title = product.get("title", "").lower()
            category = product.get("category", "").lower()
            brand = product.get("brand", "").lower()

            if any(kw.lower() in f"{title} {category} {brand}" for kw in keywords):
                matches.append(product)

            if len(matches) >= 5:
                break

        if not matches:
            return AgentResponse(
                success=True,
                message=f"'{' '.join(keywords)}' 관련 상품을 찾지 못했습니다.",
                data={"query": query, "results": []},
                suggested_actions=["다른 키워드로 검색", "카테고리 보기"],
            )

        results = [
            {
                "product_id": p.get("product_id"),
                "title": p.get("title"),
                "price": p.get("price"),
                "brand": p.get("brand"),
            }
            for p in matches
        ]

        response_text = f"{len(results)}개 상품을 찾았습니다:\n\n"
        for i, r in enumerate(results, 1):
            response_text += f"{i}. {r['title']} - {r['price']}원\n"

        return AgentResponse(
            success=True,
            message=response_text,
            data={"query": query, "results": results},
            suggested_actions=["상세 정보 보기", "가격순 정렬", "리뷰순 정렬"],
        )

    def _format_product_info(self, product: Dict[str, Any]) -> str:
        """상품 정보 포맷."""
        lines = [
            f"**{product.get('title', 'N/A')}**",
            "",
            f"- 브랜드: {product.get('brand', 'N/A')}",
            f"- 카테고리: {product.get('category', 'N/A')}",
            f"- 가격: {product.get('price', 'N/A')}원",
            f"- 평점: {product.get('avg_rating', 'N/A')}",
            f"- 재고: {product.get('stock_quantity', 'N/A')}개",
        ]
        return "\n".join(lines)

    def _extract_keywords(self, message: str) -> List[str]:
        """메시지에서 검색 키워드 추출."""
        # 불용어 제거
        stopwords = {"상품", "찾아줘", "검색", "보여줘", "알려줘", "있어", "있나요", "주세요"}
        words = message.split()
        keywords = [w for w in words if w not in stopwords and len(w) >= 2]
        return keywords[:3]  # 최대 3개

    def _get_stock_actions(self, status: str) -> List[str]:
        """재고 상태별 추천 액션."""
        if status == "품절":
            return ["재입고 알림 신청", "유사 상품 보기"]
        elif status == "품절임박":
            return ["바로 구매하기", "장바구니 담기"]
        else:
            return ["장바구니 담기", "리뷰 보기"]
