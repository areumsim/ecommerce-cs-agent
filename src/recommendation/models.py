"""추천 시스템 Pydantic 모델."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RecommendationType(str, Enum):
    """추천 유형."""
    
    SIMILAR = "similar"
    PERSONALIZED = "personalized"
    TRENDING = "trending"
    BOUGHT_TOGETHER = "bought_together"
    CATEGORY = "category"
    HYBRID = "hybrid"


class ProductRecommendation(BaseModel):
    """추천 상품."""
    
    product_id: str = Field(..., description="상품 ID")
    name: str = Field(..., description="상품명")
    price: float = Field(..., description="가격")
    score: float = Field(..., description="추천 점수 (0-1)")
    reason: str = Field(..., description="추천 이유")
    category_id: Optional[str] = Field(None, description="카테고리 ID")
    brand: Optional[str] = Field(None, description="브랜드")
    avg_rating: Optional[float] = Field(None, description="평균 평점")
    image_url: Optional[str] = Field(None, description="상품 이미지 URL")


class RecommendationRequest(BaseModel):
    """추천 요청."""
    
    # 기본 파라미터
    top_k: int = Field(10, ge=1, le=50, description="반환할 상품 수")
    
    # 유사 상품 추천용
    product_id: Optional[str] = Field(None, description="기준 상품 ID (유사/함께구매)")
    
    # 개인화 추천용
    user_id: Optional[str] = Field(None, description="사용자 ID (개인화)")
    exclude_purchased: bool = Field(True, description="구매한 상품 제외")
    
    # 인기 상품용
    period: str = Field("week", description="기간 (day/week/month)")
    
    # 카테고리 추천용
    category_id: Optional[str] = Field(None, description="카테고리 ID")
    
    # 필터링
    min_rating: float = Field(0.0, ge=0, le=5, description="최소 평점")
    min_price: Optional[float] = Field(None, description="최소 가격")
    max_price: Optional[float] = Field(None, description="최대 가격")
    
    # 추천 방식
    method: str = Field("hybrid", description="추천 방식 (collaborative/content/hybrid)")


class RecommendationResponse(BaseModel):
    """추천 응답."""
    
    recommendation_type: RecommendationType = Field(..., description="추천 유형")
    products: List[ProductRecommendation] = Field(..., description="추천 상품 목록")
    total_count: int = Field(..., description="총 추천 수")
    method_used: str = Field(..., description="사용된 추천 방식")
    query_time_ms: float = Field(..., description="쿼리 소요 시간 (ms)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    
    # 폴백 여부
    is_fallback: bool = Field(False, description="폴백 응답 여부")
    fallback_reason: Optional[str] = Field(None, description="폴백 사유")


class SimilarProductsRequest(BaseModel):
    """유사 상품 추천 요청."""
    
    product_id: str = Field(..., description="기준 상품 ID")
    top_k: int = Field(10, ge=1, le=50, description="반환할 상품 수")
    method: str = Field("hybrid", description="추천 방식")


class PersonalizedRequest(BaseModel):
    """개인화 추천 요청."""
    
    user_id: str = Field(..., description="사용자 ID")
    top_k: int = Field(10, ge=1, le=50, description="반환할 상품 수")
    category_id: Optional[str] = Field(None, description="카테고리 필터")
    exclude_purchased: bool = Field(True, description="구매 상품 제외")


class TrendingRequest(BaseModel):
    """인기 상품 요청."""
    
    period: str = Field("week", description="기간 (day/week/month)")
    category_id: Optional[str] = Field(None, description="카테고리 필터")
    top_k: int = Field(10, ge=1, le=50, description="반환할 상품 수")


class BoughtTogetherRequest(BaseModel):
    """함께 구매 상품 요청."""
    
    product_id: str = Field(..., description="기준 상품 ID")
    top_k: int = Field(10, ge=1, le=50, description="반환할 상품 수")
