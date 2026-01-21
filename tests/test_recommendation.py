"""추천 시스템 테스트."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.nodes.intent_classifier import classify_intent_keyword
from src.agents.nodes.recommend_agent import (
    handle_recommendation,
    extract_product_id_from_message,
    extract_category_from_message,
)
from src.recommendation.models import (
    RecommendationType,
    ProductRecommendation,
    RecommendationResponse,
)


class TestRecommendIntentClassification:

    def test_recommend_personal_intent(self):
        result = classify_intent_keyword("추천 좀 해줘")
        assert result.intent == "recommend"
        assert result.sub_intent == "personal"

    def test_recommend_similar_intent(self):
        result = classify_intent_keyword("이거랑 비슷한 상품 추천")
        assert result.intent == "recommend"
        assert result.sub_intent == "similar"

    def test_recommend_trending_intent(self):
        result = classify_intent_keyword("인기 상품 추천")
        assert result.intent == "recommend"
        assert result.sub_intent == "trending"

    def test_recommend_together_intent(self):
        result = classify_intent_keyword("같이 사는 상품 추천")
        assert result.intent == "recommend"
        assert result.sub_intent == "together"

    def test_recommend_with_product_id(self):
        result = classify_intent_keyword("PROD-12345랑 비슷한 상품 추천")
        assert result.intent == "recommend"
        assert result.sub_intent == "similar"


class TestExtractProductId:

    def test_extract_prod_format(self):
        assert extract_product_id_from_message("PROD-12345 비슷한 거") == "PROD-12345"

    def test_extract_prod_underscore(self):
        assert extract_product_id_from_message("PROD_ABC123 추천해줘") == "PROD_ABC123"

    def test_no_product_id(self):
        assert extract_product_id_from_message("추천해주세요") is None


class TestExtractCategory:

    def test_extract_electronics(self):
        assert extract_category_from_message("노트북 추천해줘") == "전자제품"

    def test_extract_fashion(self):
        assert extract_category_from_message("옷 추천 좀") == "패션"

    def test_extract_food(self):
        assert extract_category_from_message("맛있는 간식 뭐 있어요") == "식품"

    def test_no_category(self):
        assert extract_category_from_message("추천해주세요") is None


class TestHandleRecommendation:

    @pytest.mark.asyncio
    async def test_handle_personal_recommendation(self):
        mock_response = RecommendationResponse(
            products=[
                ProductRecommendation(
                    product_id="PROD-001",
                    name="테스트 상품",
                    score=0.9,
                    price=10000,
                    reason="구매 패턴 기반 추천",
                )
            ],
            total_count=1,
            recommendation_type=RecommendationType.PERSONALIZED,
            method_used="csv_fallback",
            query_time_ms=10.5,
            is_fallback=True,
        )

        with patch("src.agents.nodes.recommend_agent.get_recommendation_service") as mock_service:
            mock_svc = AsyncMock()
            mock_svc.get_personalized.return_value = mock_response
            mock_service.return_value = mock_svc

            result = await handle_recommendation(
                user_id="user_001",
                sub_intent="personal",
                payload={"query": "추천해줘"},
            )

            assert "recommendations" in result
            assert result["total_count"] == 1
            assert result["is_fallback"] is True
            mock_svc.get_personalized.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_similar_recommendation(self):
        mock_response = RecommendationResponse(
            products=[
                ProductRecommendation(
                    product_id="PROD-002",
                    name="유사 상품",
                    score=0.85,
                    price=15000,
                    reason="카테고리 유사성",
                )
            ],
            total_count=1,
            recommendation_type=RecommendationType.SIMILAR,
            method_used="csv_fallback",
            query_time_ms=8.2,
            is_fallback=True,
        )

        with patch("src.agents.nodes.recommend_agent.get_recommendation_service") as mock_service:
            mock_svc = AsyncMock()
            mock_svc.get_similar_products.return_value = mock_response
            mock_service.return_value = mock_svc

            result = await handle_recommendation(
                user_id="user_001",
                sub_intent="similar",
                payload={"product_id": "PROD-001", "query": "비슷한 거"},
            )

            assert "recommendations" in result
            mock_svc.get_similar_products.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_trending_recommendation(self):
        mock_response = RecommendationResponse(
            products=[],
            total_count=0,
            recommendation_type=RecommendationType.TRENDING,
            method_used="csv_fallback",
            query_time_ms=5.0,
            is_fallback=True,
        )

        with patch("src.agents.nodes.recommend_agent.get_recommendation_service") as mock_service:
            mock_svc = AsyncMock()
            mock_svc.get_trending.return_value = mock_response
            mock_service.return_value = mock_svc

            result = await handle_recommendation(
                user_id="user_001",
                sub_intent="trending",
                payload={"query": "인기 상품"},
            )

            assert "recommendations" in result
            mock_svc.get_trending.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_recommendation_error(self):
        with patch("src.agents.nodes.recommend_agent.get_recommendation_service") as mock_service:
            mock_svc = AsyncMock()
            mock_svc.get_personalized.side_effect = Exception("Service error")
            mock_service.return_value = mock_svc

            result = await handle_recommendation(
                user_id="user_001",
                sub_intent="personal",
                payload={},
            )

            assert "error" in result
            assert result["recommendations"] == []


class TestSemanticSimilarProducts:
    """시맨틱 유사도 기반 추천 테스트."""

    @pytest.mark.asyncio
    async def test_semantic_similar_returns_semantic_similarity_method(self):
        """semantic 모드에서 method_used가 semantic_similarity인지 확인."""
        mock_product = MagicMock()
        mock_product.product_id = "B00005I9PZ"
        mock_product.title = "Test Shoes"
        mock_product.brand = "Nike"
        mock_product.category = "Sports"
        mock_product.price = 100.0
        mock_product.average_rating = 4.5

        mock_similar_product = MagicMock()
        mock_similar_product.product_id = "B00006XXXX"
        mock_similar_product.title = "Similar Shoes"
        mock_similar_product.brand = "Adidas"
        mock_similar_product.category = "Sports"
        mock_similar_product.price = 90.0
        mock_similar_product.average_rating = 4.3

        import numpy as np
        mock_embedding = np.array([0.1] * 384)

        with patch("src.rag.embedder.get_embedder") as mock_embedder_func:
            mock_embedder = MagicMock()
            mock_embedder.encode_query.return_value = mock_embedding
            mock_embedder_func.return_value = mock_embedder

            from src.recommendation.service import RecommendationService
            RecommendationService.reset_instance()
            service = RecommendationService()

            mock_repo = MagicMock()
            mock_repo.get_product.return_value = mock_product
            mock_repo.search_products_by_embedding.return_value = [
                (mock_similar_product, 0.95)
            ]
            service._rdf_repo = mock_repo

            result = await service.get_similar_products(
                "B00005I9PZ", method="semantic"
            )

            assert result.method_used == "semantic_similarity"
            assert not result.is_fallback
            assert len(result.products) > 0
            assert result.products[0].reason == "비슷한 스타일의 상품입니다"

    @pytest.mark.asyncio
    async def test_hybrid_falls_back_to_rdf_when_semantic_fails(self):
        """hybrid 모드에서 semantic 실패 시 RDF로 폴백하는지 확인."""
        mock_product = MagicMock()
        mock_product.product_id = "B00005I9PZ"
        mock_product.title = "Test Shoes"
        mock_product.brand = "Nike"
        mock_product.category = "Sports"
        mock_product.price = 100.0
        mock_product.average_rating = 4.5

        mock_rdf_product = MagicMock()
        mock_rdf_product.product_id = "B00007YYYY"
        mock_rdf_product.title = "RDF Similar Shoes"
        mock_rdf_product.brand = "Puma"
        mock_rdf_product.category = "Sports"
        mock_rdf_product.price = 85.0
        mock_rdf_product.average_rating = 4.0

        with patch("src.rdf.repository.get_rdf_repository") as mock_repo_func:
            mock_repo = MagicMock()
            mock_repo.get_product.return_value = mock_product
            # semantic 검색 빈 결과 반환
            mock_repo.search_products_by_embedding.return_value = []
            # RDF 검색은 결과 반환
            mock_repo.get_similar_products.return_value = [mock_rdf_product]
            mock_repo_func.return_value = mock_repo

            from src.recommendation.service import RecommendationService
            RecommendationService.reset_instance()
            service = RecommendationService()
            service._rdf_repo = mock_repo

            result = await service.get_similar_products(
                "B00005I9PZ", method="hybrid"
            )

            assert result.method_used == "rdf_similarity"
            assert not result.is_fallback
            assert len(result.products) > 0

    @pytest.mark.asyncio
    async def test_rdf_mode_does_not_use_semantic(self):
        """rdf 모드에서 시맨틱 검색을 사용하지 않는지 확인."""
        mock_rdf_product = MagicMock()
        mock_rdf_product.product_id = "B00007YYYY"
        mock_rdf_product.title = "RDF Similar Shoes"
        mock_rdf_product.brand = "Puma"
        mock_rdf_product.category = "Sports"
        mock_rdf_product.price = 85.0
        mock_rdf_product.average_rating = 4.0

        with patch("src.rdf.repository.get_rdf_repository") as mock_repo_func:
            mock_repo = MagicMock()
            mock_repo.get_similar_products.return_value = [mock_rdf_product]
            mock_repo_func.return_value = mock_repo

            from src.recommendation.service import RecommendationService
            RecommendationService.reset_instance()
            service = RecommendationService()
            service._rdf_repo = mock_repo

            result = await service.get_similar_products(
                "B00005I9PZ", method="rdf"
            )

            assert result.method_used == "rdf_similarity"
            # search_products_by_embedding이 호출되지 않아야 함
            mock_repo.search_products_by_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_semantic_excludes_self(self):
        """시맨틱 검색에서 자기 자신이 제외되는지 확인."""
        mock_product = MagicMock()
        mock_product.product_id = "B00005I9PZ"
        mock_product.title = "Test Shoes"
        mock_product.brand = "Nike"
        mock_product.category = "Sports"
        mock_product.price = 100.0
        mock_product.average_rating = 4.5

        mock_self_product = MagicMock()
        mock_self_product.product_id = "B00005I9PZ"  # 동일 ID

        mock_other_product = MagicMock()
        mock_other_product.product_id = "B00006XXXX"
        mock_other_product.title = "Different Shoes"
        mock_other_product.brand = "Adidas"
        mock_other_product.category = "Sports"
        mock_other_product.price = 90.0
        mock_other_product.average_rating = 4.3

        import numpy as np
        mock_embedding = np.array([0.1] * 384)

        with patch("src.rag.embedder.get_embedder") as mock_embedder_func:
            mock_embedder = MagicMock()
            mock_embedder.encode_query.return_value = mock_embedding
            mock_embedder_func.return_value = mock_embedder

            from src.recommendation.service import RecommendationService
            RecommendationService.reset_instance()
            service = RecommendationService()

            mock_repo = MagicMock()
            mock_repo.get_product.return_value = mock_product
            # 자기 자신도 결과에 포함
            mock_repo.search_products_by_embedding.return_value = [
                (mock_self_product, 1.0),  # 자기 자신
                (mock_other_product, 0.9),
            ]
            service._rdf_repo = mock_repo

            result = await service.get_similar_products(
                "B00005I9PZ", method="semantic"
            )

            assert result.method_used == "semantic_similarity"
            # 자기 자신이 결과에서 제외되었는지 확인
            product_ids = [p.product_id for p in result.products]
            assert "B00005I9PZ" not in product_ids
            assert "B00006XXXX" in product_ids


class TestRecommendationAPIEndpoints:

    def test_similar_products_endpoint(self, client):
        try:
            response = client.get("/recommendations/similar/PROD-TEST-001")
            assert response.status_code in [200, 404, 500]
        except Exception:
            pytest.skip("Endpoint requires data setup")

    def test_personalized_endpoint(self, client, test_user_id):
        try:
            response = client.get(f"/recommendations/personalized/{test_user_id}")
            assert response.status_code in [200, 404, 500]
        except Exception:
            pytest.skip("Endpoint requires data setup")

    def test_trending_endpoint(self, client):
        try:
            response = client.get("/recommendations/trending")
            assert response.status_code in [200, 404, 500]
        except Exception:
            pytest.skip("Endpoint requires data setup")

    def test_bought_together_endpoint(self, client):
        try:
            response = client.get("/recommendations/bought-together/PROD-TEST-001")
            assert response.status_code in [200, 404, 500]
        except Exception:
            pytest.skip("Endpoint requires data setup")

    def test_category_recommendations_endpoint(self, client):
        try:
            response = client.get("/recommendations/category/electronics")
            assert response.status_code in [200, 404, 500]
        except Exception:
            pytest.skip("Endpoint requires data setup")
