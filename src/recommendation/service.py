from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import (
    ProductRecommendation,
    RecommendationResponse,
    RecommendationType,
)

logger = logging.getLogger(__name__)


def _load_recommendation_config() -> Dict[str, Any]:
    config_path = Path("configs/recommendation.yaml")
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class RecommendationService:
    _instance: Optional["RecommendationService"] = None
    
    def __init__(self):
        self._config = _load_recommendation_config()
        self._rdf_repo = None
        
    @classmethod
    def get_instance(cls) -> "RecommendationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
    
    @property
    def rdf_repo(self):
        if self._rdf_repo is None:
            try:
                from src.rdf.repository import get_rdf_repository
                self._rdf_repo = get_rdf_repository()
            except Exception as e:
                logger.warning(f"RDF repository initialization failed: {e}")
        return self._rdf_repo
    
    def is_available(self) -> bool:
        return self.rdf_repo is not None
    
    def _rdf_product_to_recommendation(
        self,
        product,
        score: float = 0.5,
        reason: str = "추천 상품입니다",
    ) -> ProductRecommendation:
        return ProductRecommendation(
            product_id=product.product_id,
            name=product.title,
            price=product.price,
            score=score,
            reason=reason,
            category_id=product.category,
            brand=product.brand,
            avg_rating=product.average_rating if product.average_rating else None,
            image_url=None,
        )
    
    async def get_similar_products(
        self,
        product_id: str,
        top_k: int = 10,
        method: str = "hybrid",
    ) -> RecommendationResponse:
        """유사 상품 추천.

        Args:
            product_id: 기준 상품 ID
            top_k: 반환할 상품 수
            method: "rdf" | "semantic" | "hybrid"
                - rdf: RDF similarTo 관계만 사용
                - semantic: 벡터 유사도 검색만 사용
                - hybrid: semantic 먼저 시도, 실패 시 rdf 폴백
        """
        start_time = time.time()

        # Semantic 모드 (벡터 유사도 검색)
        if method in ("semantic", "hybrid") and self.rdf_repo:
            try:
                semantic_result = await self._get_semantic_similar(product_id, top_k, start_time)
                if semantic_result and semantic_result.products:
                    return semantic_result
            except Exception as e:
                logger.warning(f"Semantic similarity search failed: {e}")
                if method == "semantic":
                    return RecommendationResponse(
                        recommendation_type=RecommendationType.SIMILAR,
                        products=[],
                        total_count=0,
                        method_used="semantic_fallback",
                        query_time_ms=(time.time() - start_time) * 1000,
                        is_fallback=True,
                        fallback_reason=f"시맨틱 검색 실패: {e}",
                    )

        # RDF 모드 (similarTo 관계 기반)
        if method in ("rdf", "hybrid") and self.rdf_repo:
            try:
                products = self.rdf_repo.get_similar_products(product_id, limit=top_k)
                if products:
                    recommendations = [
                        self._rdf_product_to_recommendation(p, 0.8, "유사한 상품입니다")
                        for p in products
                    ]
                    return RecommendationResponse(
                        recommendation_type=RecommendationType.SIMILAR,
                        products=recommendations,
                        total_count=len(recommendations),
                        method_used="rdf_similarity",
                        query_time_ms=(time.time() - start_time) * 1000,
                        is_fallback=False,
                        fallback_reason=None,
                    )
            except Exception as e:
                logger.warning(f"RDF similar products failed: {e}")

        return RecommendationResponse(
            recommendation_type=RecommendationType.SIMILAR,
            products=[],
            total_count=0,
            method_used="fallback",
            query_time_ms=(time.time() - start_time) * 1000,
            is_fallback=True,
            fallback_reason="RDF 조회 실패",
        )

    async def _get_semantic_similar(
        self,
        product_id: str,
        top_k: int,
        start_time: float,
    ) -> Optional[RecommendationResponse]:
        """벡터 유사도 기반 유사 상품 검색."""
        # 1. 기준 상품 조회
        product = self.rdf_repo.get_product(product_id)
        if not product:
            logger.warning(f"Product not found: {product_id}")
            return None

        # 2. 쿼리 임베딩 생성
        from src.rag.embedder import get_embedder
        embedder = get_embedder()

        query_text = f"{product.title} {product.brand} {product.category}"
        query_embedding = embedder.encode_query(query_text)

        # 3. 벡터 유사도 검색
        similar = self.rdf_repo.search_products_by_embedding(
            query_embedding.tolist(), top_k=top_k * 2
        )

        if not similar:
            return None

        # 4. 자기 자신 제외
        similar = [(p, s) for p, s in similar if p.product_id != product_id]

        if not similar:
            return None

        # 5. 결과 변환
        recommendations = [
            self._rdf_product_to_recommendation(
                p, float(score), "비슷한 스타일의 상품입니다"
            )
            for p, score in similar[:top_k]
        ]

        return RecommendationResponse(
            recommendation_type=RecommendationType.SIMILAR,
            products=recommendations,
            total_count=len(recommendations),
            method_used="semantic_similarity",
            query_time_ms=(time.time() - start_time) * 1000,
            is_fallback=False,
            fallback_reason=None,
        )
    
    async def get_personalized(
        self,
        user_id: str,
        top_k: int = 10,
        category_id: Optional[str] = None,
        exclude_purchased: bool = True,
    ) -> RecommendationResponse:
        start_time = time.time()
        
        if self.rdf_repo:
            try:
                results = self.rdf_repo.get_collaborative_recommendations(user_id, limit=top_k)
                if results:
                    recommendations = [
                        self._rdf_product_to_recommendation(
                            product, 
                            min(1.0, score / 10), 
                            f"비슷한 취향의 고객 {score}명이 구매한 상품입니다"
                        )
                        for product, score in results
                    ]
                    if category_id:
                        recommendations = [r for r in recommendations if r.category_id == category_id]
                    
                    return RecommendationResponse(
                        recommendation_type=RecommendationType.PERSONALIZED,
                        products=recommendations[:top_k],
                        total_count=len(recommendations),
                        method_used="rdf_collaborative",
                        query_time_ms=(time.time() - start_time) * 1000,
                        is_fallback=False,
                        fallback_reason=None,
                    )
            except Exception as e:
                logger.warning(f"RDF personalized failed: {e}")
        
        return await self._fallback_personalized(top_k, category_id, start_time)
    
    async def _fallback_personalized(
        self,
        top_k: int,
        category_id: Optional[str],
        start_time: float,
    ) -> RecommendationResponse:
        if self.rdf_repo:
            try:
                products = self.rdf_repo.get_products(category=category_id, limit=top_k * 2)
                products = sorted(products, key=lambda p: p.average_rating or 0, reverse=True)[:top_k]
                recommendations = [
                    self._rdf_product_to_recommendation(p, 0.5, "인기 상품입니다")
                    for p in products
                ]
                return RecommendationResponse(
                    recommendation_type=RecommendationType.PERSONALIZED,
                    products=recommendations,
                    total_count=len(recommendations),
                    method_used="rdf_popularity",
                    query_time_ms=(time.time() - start_time) * 1000,
                    is_fallback=True,
                    fallback_reason="협업 필터링 결과 없음, 인기 상품으로 대체",
                )
            except Exception as e:
                logger.warning(f"RDF fallback failed: {e}")
        
        return RecommendationResponse(
            recommendation_type=RecommendationType.PERSONALIZED,
            products=[],
            total_count=0,
            method_used="fallback",
            query_time_ms=(time.time() - start_time) * 1000,
            is_fallback=True,
            fallback_reason="RDF 조회 실패",
        )
    
    async def get_trending(
        self,
        period: str = "week",
        category_id: Optional[str] = None,
        top_k: int = 10,
    ) -> RecommendationResponse:
        start_time = time.time()
        
        if self.rdf_repo:
            try:
                products = self.rdf_repo.get_products(category=category_id, limit=top_k * 3)
                
                def popularity_score(p):
                    rating = p.average_rating or 0
                    reviews = p.rating_number or 1
                    return rating * (1 + 0.1 * min(reviews, 100))
                
                products = sorted(products, key=popularity_score, reverse=True)[:top_k]
                recommendations = [
                    self._rdf_product_to_recommendation(
                        p, 
                        min(1.0, popularity_score(p) / 10), 
                        "인기 상품입니다"
                    )
                    for p in products
                ]
                return RecommendationResponse(
                    recommendation_type=RecommendationType.TRENDING,
                    products=recommendations,
                    total_count=len(recommendations),
                    method_used="rdf_popularity",
                    query_time_ms=(time.time() - start_time) * 1000,
                    is_fallback=False,
                    fallback_reason=None,
                    metadata={"period": period},
                )
            except Exception as e:
                logger.warning(f"RDF trending failed: {e}")
        
        return RecommendationResponse(
            recommendation_type=RecommendationType.TRENDING,
            products=[],
            total_count=0,
            method_used="fallback",
            query_time_ms=(time.time() - start_time) * 1000,
            is_fallback=True,
            fallback_reason="RDF 조회 실패",
            metadata={"period": period},
        )
    
    async def get_bought_together(
        self,
        product_id: str,
        top_k: int = 10,
    ) -> RecommendationResponse:
        start_time = time.time()
        
        if self.rdf_repo:
            try:
                products = self.rdf_repo.get_similar_products(product_id, limit=top_k)
                if products:
                    recommendations = [
                        self._rdf_product_to_recommendation(p, 0.7, "함께 구매하면 좋은 상품입니다")
                        for p in products
                    ]
                    return RecommendationResponse(
                        recommendation_type=RecommendationType.BOUGHT_TOGETHER,
                        products=recommendations,
                        total_count=len(recommendations),
                        method_used="rdf_similarity",
                        query_time_ms=(time.time() - start_time) * 1000,
                        is_fallback=False,
                        fallback_reason=None,
                    )
            except Exception as e:
                logger.warning(f"RDF bought_together failed: {e}")
        
        return RecommendationResponse(
            recommendation_type=RecommendationType.BOUGHT_TOGETHER,
            products=[],
            total_count=0,
            method_used="fallback",
            query_time_ms=(time.time() - start_time) * 1000,
            is_fallback=True,
            fallback_reason="RDF 조회 실패",
        )
    
    async def get_category_recommendations(
        self,
        category_id: str,
        top_k: int = 10,
        min_rating: float = 3.0,
    ) -> RecommendationResponse:
        start_time = time.time()
        
        if self.rdf_repo:
            try:
                products = self.rdf_repo.get_products(category=category_id, limit=top_k * 2)
                products = [p for p in products if (p.average_rating or 0) >= min_rating]
                products = sorted(products, key=lambda p: p.average_rating or 0, reverse=True)[:top_k]
                
                recommendations = [
                    self._rdf_product_to_recommendation(
                        p, 
                        (p.average_rating or 0) / 5, 
                        "카테고리 인기 상품입니다"
                    )
                    for p in products
                ]
                return RecommendationResponse(
                    recommendation_type=RecommendationType.CATEGORY,
                    products=recommendations,
                    total_count=len(recommendations),
                    method_used="rdf_category",
                    query_time_ms=(time.time() - start_time) * 1000,
                    is_fallback=False,
                    fallback_reason=None,
                    metadata={"category_id": category_id},
                )
            except Exception as e:
                logger.warning(f"RDF category failed: {e}")
        
        return RecommendationResponse(
            recommendation_type=RecommendationType.CATEGORY,
            products=[],
            total_count=0,
            method_used="fallback",
            query_time_ms=(time.time() - start_time) * 1000,
            is_fallback=True,
            fallback_reason="RDF 조회 실패",
            metadata={"category_id": category_id},
        )


def get_recommendation_service() -> RecommendationService:
    return RecommendationService.get_instance()
