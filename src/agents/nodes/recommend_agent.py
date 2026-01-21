"""추천 에이전트 노드.

추천 의도 처리를 담당합니다.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from src.recommendation import get_recommendation_service

logger = logging.getLogger(__name__)


async def handle_recommendation(
    user_id: str,
    sub_intent: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """추천 의도 처리.
    
    Args:
        user_id: 사용자 ID
        sub_intent: 세부 의도 (similar/personal/trending/together/category)
        payload: 요청 페이로드
        
    Returns:
        추천 결과
    """
    service = get_recommendation_service()
    
    top_k = int(payload.get("top_k", 10))
    product_id = payload.get("product_id", "")
    category_id = payload.get("category_id", "")
    
    try:
        if sub_intent == "similar" and product_id:
            method = payload.get("method", "hybrid")
            result = await service.get_similar_products(
                product_id=product_id,
                top_k=top_k,
                method=method,
            )
        elif sub_intent == "together" and product_id:
            result = await service.get_bought_together(
                product_id=product_id,
                top_k=top_k,
            )
        elif sub_intent == "trending":
            period = payload.get("period", "week")
            result = await service.get_trending(
                period=period,
                category_id=category_id if category_id else None,
                top_k=top_k,
            )
        elif sub_intent == "category" and category_id:
            min_rating = float(payload.get("min_rating", 3.0))
            result = await service.get_category_recommendations(
                category_id=category_id,
                top_k=top_k,
                min_rating=min_rating,
            )
        else:
            # 기본: 개인화 추천
            result = await service.get_personalized(
                user_id=user_id,
                top_k=top_k,
                category_id=category_id if category_id else None,
                exclude_purchased=payload.get("exclude_purchased", True),
            )
        
        return {
            "recommendations": [p.model_dump() for p in result.products],
            "total_count": result.total_count,
            "method_used": result.method_used,
            "recommendation_type": result.recommendation_type.value,
            "is_fallback": result.is_fallback,
        }
        
    except Exception as e:
        logger.error(f"추천 처리 실패: {e}")
        return {
            "error": str(e),
            "recommendations": [],
            "total_count": 0,
        }


def extract_product_id_from_message(message: str) -> Optional[str]:
    """메시지에서 상품 ID 추출."""
    pattern = r"\b(PROD[-_][A-Za-z0-9_-]+|[A-Z0-9]{10})\b"
    match = re.search(pattern, message)
    return match.group(0) if match else None


def extract_category_from_message(message: str) -> Optional[str]:
    """메시지에서 카테고리 키워드 추출."""
    category_keywords = {
        "전자제품": ["전자", "가전", "디지털", "컴퓨터", "노트북", "핸드폰", "스마트폰"],
        "패션": ["옷", "의류", "패션", "신발", "가방", "액세서리"],
        "식품": ["음식", "식품", "간식", "음료", "과일", "채소"],
        "가구": ["가구", "인테리어", "소파", "침대", "테이블"],
        "도서": ["책", "도서", "서적", "문구"],
        "스포츠": ["운동", "스포츠", "헬스", "피트니스"],
        "뷰티": ["화장품", "뷰티", "스킨케어", "메이크업"],
    }
    
    message_lower = message.lower()
    for category, keywords in category_keywords.items():
        if any(kw in message_lower for kw in keywords):
            return category
    
    return None
