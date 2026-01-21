"""그래프 레포지토리 모듈.

Neo4j 기반 CRUD 및 추천 쿼리 제공.
인메모리 그래프 폴백 지원.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .connection import GraphConnection, get_graph_connection, is_graph_available

logger = logging.getLogger(__name__)

# 인메모리 그래프 폴백
_inmemory_module = None
try:
    from . import inmemory as _inmemory_module
except ImportError:
    pass


@dataclass
class ProductNode:
    """상품 노드."""
    
    product_id: str
    name: str
    price: float
    category_id: str
    brand: str
    avg_rating: float
    review_count: int
    stock_status: str


@dataclass
class CustomerNode:
    """고객 노드."""
    
    customer_id: str
    email: str
    name: str
    segment: str
    created_at: str


@dataclass
class RecommendationResult:
    """추천 결과."""
    
    product_id: str
    name: str
    price: float
    score: float
    reason: str
    category_id: Optional[str] = None
    brand: Optional[str] = None
    avg_rating: Optional[float] = None


class GraphRepository:
    """그래프 DB 레포지토리.
    
    Neo4j 기반 노드/관계 CRUD 및 추천 쿼리 제공.
    인메모리 그래프로 자동 폴백.
    """
    
    _instance: Optional["GraphRepository"] = None
    
    def __init__(self, connection: Optional[GraphConnection] = None):
        self._connection = connection
        self._inmemory = None
        
    @property
    def connection(self) -> GraphConnection:
        if self._connection is None:
            self._connection = get_graph_connection()
        return self._connection
    
    @property
    def inmemory(self):
        if self._inmemory is None and _inmemory_module:
            self._inmemory = _inmemory_module.get_inmemory_graph()
        return self._inmemory
    
    def _use_neo4j(self) -> bool:
        return self.connection.is_available()
    
    def _use_inmemory(self) -> bool:
        return self.inmemory is not None and self.inmemory.is_available()
    
    @classmethod
    def get_instance(cls) -> "GraphRepository":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
    
    def is_available(self) -> bool:
        return self._use_neo4j() or self._use_inmemory()
    
    # ============================================
    # 노드 CRUD
    # ============================================
    
    async def create_product(self, product: Dict[str, Any]) -> bool:
        """상품 노드 생성."""
        query = """
        MERGE (p:Product {product_id: $product_id})
        SET p.name = $name,
            p.price = $price,
            p.category_id = $category_id,
            p.brand = $brand,
            p.avg_rating = $avg_rating,
            p.review_count = $review_count,
            p.stock_status = $stock_status,
            p.updated_at = datetime()
        """
        try:
            nodes, _ = await self.connection.execute_write_async(query, product)
            return True
        except Exception as e:
            logger.error(f"상품 노드 생성 실패: {e}")
            return False
    
    async def create_customer(self, customer: Dict[str, Any]) -> bool:
        """고객 노드 생성."""
        query = """
        MERGE (c:Customer {customer_id: $customer_id})
        SET c.email = $email,
            c.name = $name,
            c.segment = $segment,
            c.created_at = $created_at,
            c.updated_at = datetime()
        """
        try:
            await self.connection.execute_write_async(query, customer)
            return True
        except Exception as e:
            logger.error(f"고객 노드 생성 실패: {e}")
            return False
    
    async def create_category(self, category: Dict[str, Any]) -> bool:
        """카테고리 노드 생성."""
        query = """
        MERGE (cat:Category {category_id: $category_id})
        SET cat.name = $name,
            cat.level = $level,
            cat.parent_id = $parent_id
        """
        try:
            await self.connection.execute_write_async(query, category)
            return True
        except Exception as e:
            logger.error(f"카테고리 노드 생성 실패: {e}")
            return False
    
    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """상품 노드 조회."""
        query = """
        MATCH (p:Product {product_id: $product_id})
        RETURN p {.*} AS product
        """
        try:
            results = await self.connection.execute_query_async(query, {"product_id": product_id})
            if results:
                return results[0].get("product")
            return None
        except Exception as e:
            logger.error(f"상품 조회 실패: {e}")
            return None
    
    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """고객 노드 조회."""
        query = """
        MATCH (c:Customer {customer_id: $customer_id})
        RETURN c {.*} AS customer
        """
        try:
            results = await self.connection.execute_query_async(query, {"customer_id": customer_id})
            if results:
                return results[0].get("customer")
            return None
        except Exception as e:
            logger.error(f"고객 조회 실패: {e}")
            return None
    
    # ============================================
    # 관계 생성
    # ============================================
    
    async def create_purchase_relationship(
        self,
        customer_id: str,
        product_id: str,
        order_id: str,
        purchased_at: str,
        quantity: int = 1,
        unit_price: float = 0.0,
    ) -> bool:
        """구매 관계 생성."""
        query = """
        MATCH (c:Customer {customer_id: $customer_id})
        MATCH (p:Product {product_id: $product_id})
        MERGE (c)-[r:PURCHASED {order_id: $order_id}]->(p)
        SET r.purchased_at = datetime($purchased_at),
            r.quantity = $quantity,
            r.unit_price = $unit_price
        """
        try:
            await self.connection.execute_write_async(query, {
                "customer_id": customer_id,
                "product_id": product_id,
                "order_id": order_id,
                "purchased_at": purchased_at,
                "quantity": quantity,
                "unit_price": unit_price,
            })
            return True
        except Exception as e:
            logger.error(f"구매 관계 생성 실패: {e}")
            return False
    
    async def create_category_relationship(
        self,
        product_id: str,
        category_id: str,
    ) -> bool:
        """상품-카테고리 관계 생성."""
        query = """
        MATCH (p:Product {product_id: $product_id})
        MATCH (cat:Category {category_id: $category_id})
        MERGE (p)-[:BELONGS_TO]->(cat)
        """
        try:
            await self.connection.execute_write_async(query, {
                "product_id": product_id,
                "category_id": category_id,
            })
            return True
        except Exception as e:
            logger.error(f"카테고리 관계 생성 실패: {e}")
            return False
    
    async def create_similarity_relationship(
        self,
        product1_id: str,
        product2_id: str,
        score: float,
        method: str = "hybrid",
    ) -> bool:
        """상품 유사도 관계 생성."""
        query = """
        MATCH (p1:Product {product_id: $product1_id})
        MATCH (p2:Product {product_id: $product2_id})
        MERGE (p1)-[r:SIMILAR_TO]-(p2)
        SET r.score = $score,
            r.method = $method,
            r.updated_at = datetime()
        """
        try:
            await self.connection.execute_write_async(query, {
                "product1_id": product1_id,
                "product2_id": product2_id,
                "score": score,
                "method": method,
            })
            return True
        except Exception as e:
            logger.error(f"유사도 관계 생성 실패: {e}")
            return False
    
    # ============================================
    # 추천 쿼리
    # ============================================
    
    async def get_similar_products(
        self,
        product_id: str,
        top_k: int = 10,
        method: Optional[str] = None,
    ) -> List[RecommendationResult]:
        if self._use_inmemory() and not self._use_neo4j() and self.inmemory:
            results = self.inmemory.get_similar_products(product_id, top_k)
            return [self._dict_to_result(r) for r in results]
        
        query = """
        MATCH (p:Product {product_id: $product_id})
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(cat:Category)<-[:BELONGS_TO]-(similar:Product)
        WHERE similar.product_id <> p.product_id
        WITH p, similar,
             CASE WHEN similar.category_id = p.category_id THEN 0.4 ELSE 0 END +
             CASE WHEN similar.brand = p.brand THEN 0.2 ELSE 0 END +
             CASE WHEN abs(similar.price - p.price) / p.price < 0.3 THEN 0.2 ELSE 0 END +
             CASE WHEN abs(similar.avg_rating - p.avg_rating) < 1.0 THEN 0.2 ELSE 0 END AS score
        WHERE similar IS NOT NULL AND score > 0
        RETURN similar.product_id AS product_id, similar.name AS name, similar.price AS price,
               similar.category_id AS category_id, similar.brand AS brand, similar.avg_rating AS avg_rating, score
        ORDER BY score DESC, similar.avg_rating DESC
        LIMIT $top_k
        """
        try:
            results = await self.connection.execute_query_async(query, {"product_id": product_id, "top_k": top_k})
            return [self._record_to_result(r, "이 상품과 유사한 상품입니다") for r in results]
        except Exception as e:
            logger.error(f"유사 상품 조회 실패: {e}")
            return []
    
    def _dict_to_result(self, d: Dict[str, Any]) -> RecommendationResult:
        return RecommendationResult(
            product_id=d["product_id"],
            name=d.get("name", ""),
            price=float(d.get("price", 0)),
            score=float(d.get("score", 0)),
            reason=d.get("reason", ""),
            category_id=d.get("category_id"),
            brand=d.get("brand"),
            avg_rating=float(d["avg_rating"]) if d.get("avg_rating") else None,
        )
    
    def _record_to_result(self, r: Dict[str, Any], reason: str) -> RecommendationResult:
        return RecommendationResult(
            product_id=r["product_id"],
            name=r["name"],
            price=float(r["price"]) if r["price"] else 0.0,
            score=float(r["score"]) if r["score"] else 0.0,
            reason=reason,
            category_id=r.get("category_id"),
            brand=r.get("brand"),
            avg_rating=float(r["avg_rating"]) if r.get("avg_rating") else None,
        )
    
    async def get_personalized_recommendations(
        self,
        customer_id: str,
        top_k: int = 10,
        exclude_purchased: bool = True,
    ) -> List[RecommendationResult]:
        if self._use_inmemory() and not self._use_neo4j() and self.inmemory:
            results = self.inmemory.get_personalized_recommendations(customer_id, top_k, exclude_purchased)
            return [self._dict_to_result(r) for r in results]
        
        exclude_clause = "AND NOT (me)-[:PURCHASED]->(rec)" if exclude_purchased else ""
        query = f"""
        MATCH (me:Customer {{customer_id: $customer_id}})-[:PURCHASED]->(p:Product)<-[:PURCHASED]-(other:Customer)
        WHERE me <> other
        WITH other, COUNT(p) AS common_purchases ORDER BY common_purchases DESC LIMIT 50
        MATCH (other)-[:PURCHASED]->(rec:Product)
        WHERE rec.stock_status <> 'out_of_stock' {exclude_clause}
        WITH rec, COUNT(DISTINCT other) AS score, COLLECT(DISTINCT other.customer_id) AS similar_customers
        RETURN rec.product_id AS product_id, rec.name AS name, rec.price AS price,
               rec.category_id AS category_id, rec.brand AS brand, rec.avg_rating AS avg_rating,
               score, size(similar_customers) AS similar_customer_count
        ORDER BY score DESC, rec.avg_rating DESC LIMIT $top_k
        """
        try:
            results = await self.connection.execute_query_async(query, {"customer_id": customer_id, "top_k": top_k})
            return [
                RecommendationResult(
                    product_id=r["product_id"], name=r["name"],
                    price=float(r["price"]) if r["price"] else 0.0,
                    score=float(r["score"]) if r["score"] else 0.0,
                    reason=f"비슷한 취향의 {r.get('similar_customer_count', 0)}명이 구매한 상품입니다",
                    category_id=r.get("category_id"), brand=r.get("brand"),
                    avg_rating=float(r["avg_rating"]) if r.get("avg_rating") else None,
                ) for r in results
            ]
        except Exception as e:
            logger.error(f"개인화 추천 조회 실패: {e}")
            return []
    
    async def get_bought_together(
        self,
        product_id: str,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        if self._use_inmemory() and not self._use_neo4j() and self.inmemory:
            results = self.inmemory.get_bought_together(product_id, top_k)
            return [self._dict_to_result(r) for r in results]
        
        query = """
        MATCH (p:Product {product_id: $product_id})<-[:PURCHASED]-(c:Customer)-[:PURCHASED]->(other:Product)
        WHERE p <> other
        WITH other, COUNT(DISTINCT c) AS frequency
        RETURN other.product_id AS product_id, other.name AS name, other.price AS price,
               other.category_id AS category_id, other.brand AS brand, other.avg_rating AS avg_rating, frequency AS score
        ORDER BY frequency DESC LIMIT $top_k
        """
        try:
            results = await self.connection.execute_query_async(query, {"product_id": product_id, "top_k": top_k})
            return [self._record_to_result(r, "이 상품과 함께 구매하면 좋은 상품입니다") for r in results
            ]
        except Exception as e:
            logger.error(f"함께 구매 상품 조회 실패: {e}")
            return []
    
    async def get_trending_products(
        self,
        period_days: int = 7,
        category_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        if self._use_inmemory() and not self._use_neo4j() and self.inmemory:
            results = self.inmemory.get_trending_products(period_days, category_id, top_k)
            return [self._dict_to_result(r) for r in results]
        
        category_clause = "AND (p)-[:BELONGS_TO]->(:Category {category_id: $category_id})" if category_id else ""
        query = f"""
        MATCH (c:Customer)-[r:PURCHASED]->(p:Product)
        WHERE r.purchased_at >= datetime() - duration({{days: $period_days}}) {category_clause}
        WITH p, COUNT(DISTINCT c) AS purchase_count, COUNT(r) AS total_quantity
        RETURN p.product_id AS product_id, p.name AS name, p.price AS price,
               p.category_id AS category_id, p.brand AS brand, p.avg_rating AS avg_rating,
               purchase_count, total_quantity, purchase_count * 0.7 + p.avg_rating * 0.3 AS score
        ORDER BY score DESC LIMIT $top_k
        """
        params: Dict[str, Any] = {"period_days": period_days, "top_k": top_k}
        if category_id:
            params["category_id"] = category_id
            
        try:
            results = await self.connection.execute_query_async(query, params)
            return [
                RecommendationResult(
                    product_id=r["product_id"], name=r["name"],
                    price=float(r["price"]) if r["price"] else 0.0,
                    score=float(r["score"]) if r["score"] else 0.0,
                    reason=f"최근 {r.get('purchase_count', 0)}명이 구매한 인기 상품입니다",
                    category_id=r.get("category_id"), brand=r.get("brand"),
                    avg_rating=float(r["avg_rating"]) if r.get("avg_rating") else None,
                ) for r in results
            ]
        except Exception as e:
            logger.error(f"인기 상품 조회 실패: {e}")
            return []
    
    async def get_category_recommendations(
        self,
        category_id: str,
        top_k: int = 10,
        min_rating: float = 3.0,
    ) -> List[RecommendationResult]:
        if self._use_inmemory() and not self._use_neo4j() and self.inmemory:
            results = self.inmemory.get_category_recommendations(category_id, top_k, min_rating)
            return [self._dict_to_result(r) for r in results]
        
        query = """
        MATCH (p:Product)-[:BELONGS_TO]->(:Category {category_id: $category_id})
        WHERE p.avg_rating >= $min_rating AND p.stock_status <> 'out_of_stock'
        RETURN p.product_id AS product_id, p.name AS name, p.price AS price,
               p.category_id AS category_id, p.brand AS brand, p.avg_rating AS avg_rating,
               p.review_count AS review_count, p.avg_rating * 0.6 + log(p.review_count + 1) * 0.4 AS score
        ORDER BY score DESC LIMIT $top_k
        """
        try:
            results = await self.connection.execute_query_async(query, {
                "category_id": category_id, "min_rating": min_rating, "top_k": top_k,
            })
            return [self._record_to_result(r, "이 카테고리의 인기 상품입니다") for r in results]
        except Exception as e:
            logger.error(f"카테고리 추천 조회 실패: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, int]:
        if self._use_inmemory() and not self._use_neo4j():
            return self.inmemory.get_stats() if self.inmemory else {}
        
        query = """
        MATCH (p:Product) WITH COUNT(p) AS products
        MATCH (c:Customer) WITH products, COUNT(c) AS customers
        MATCH (cat:Category) WITH products, customers, COUNT(cat) AS categories
        MATCH ()-[r:PURCHASED]->() WITH products, customers, categories, COUNT(r) AS purchases
        MATCH ()-[s:SIMILAR_TO]-() WITH products, customers, categories, purchases, COUNT(s) AS similarities
        RETURN products, customers, categories, purchases, similarities
        """
        try:
            results = await self.connection.execute_query_async(query)
            if results:
                return dict(results[0])
            return {}
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}


# 편의 함수
def get_graph_repository() -> GraphRepository:
    """그래프 레포지토리 인스턴스 반환."""
    return GraphRepository.get_instance()
