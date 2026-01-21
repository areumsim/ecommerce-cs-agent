"""인메모리 그래프 백엔드.

Neo4j 서버 없이 NetworkX를 사용한 그래프 추천 제공.
컨테이너 환경에서 Neo4j 없이도 그래프 기반 추천 가능.
"""

from __future__ import annotations

import csv
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx 미설치 - 인메모리 그래프 비활성화")


@dataclass
class ProductData:
    """상품 데이터."""
    product_id: str
    name: str = ""
    price: float = 0.0
    category_id: str = ""
    brand: str = ""
    avg_rating: float = 0.0
    review_count: int = 0
    stock_status: str = "in_stock"


@dataclass
class CustomerData:
    """고객 데이터."""
    customer_id: str
    name: str = ""
    email: str = ""
    segment: str = "Regular"


@dataclass
class PurchaseData:
    """구매 데이터."""
    customer_id: str
    product_id: str
    order_id: str
    purchased_at: str
    quantity: int = 1
    unit_price: float = 0.0


class InMemoryGraph:
    """NetworkX 기반 인메모리 그래프.
    
    Neo4j 대체용으로 CSV 데이터를 로드하여 그래프 구축.
    """
    
    _instance: Optional["InMemoryGraph"] = None
    
    def __init__(self):
        """초기화."""
        self._graph: Optional[nx.DiGraph] = None
        self._products: Dict[str, ProductData] = {}
        self._customers: Dict[str, CustomerData] = {}
        self._categories: Set[str] = set()
        self._loaded = False
        self._load_error: Optional[str] = None
    
    @classmethod
    def get_instance(cls) -> "InMemoryGraph":
        """싱글톤 인스턴스."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 리셋."""
        cls._instance = None
    
    @property
    def graph(self) -> Optional[nx.DiGraph]:
        return self._graph
    
    def is_available(self) -> bool:
        """사용 가능 여부."""
        if not HAS_NETWORKX:
            return False
        if not self._loaded:
            self.load_data()
        return self._loaded and self._graph is not None
    
    def get_status(self) -> Dict[str, Any]:
        """그래프 상태 조회."""
        if not self._loaded:
            self.load_data()
        
        if not self._graph:
            return {
                "type": "inmemory",
                "connected": False,
                "error": self._load_error or "그래프 미로드",
            }
        
        return {
            "type": "inmemory",
            "connected": True,
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
            "products": len(self._products),
            "customers": len(self._customers),
            "categories": len(self._categories),
        }
    
    def load_data(self, data_dir: Optional[Path] = None) -> bool:
        """CSV 데이터 로드 및 그래프 구축."""
        if self._loaded:
            return True
        
        if not HAS_NETWORKX:
            self._load_error = "NetworkX 미설치"
            return False
        
        data_dir = data_dir or Path("data/mock_csv")
        
        try:
            self._graph = nx.DiGraph()
            
            # 사용자 로드
            users_path = data_dir / "users.csv"
            if users_path.exists():
                self._load_users(users_path)
            
            # 상품 생성 (order_items에서 추출)
            items_path = data_dir / "order_items.csv"
            orders_path = data_dir / "orders.csv"
            
            if items_path.exists() and orders_path.exists():
                self._load_orders_and_products(orders_path, items_path)
            
            # 상품 캐시 로드 (있으면)
            products_cache = data_dir / "products_cache.csv"
            if products_cache.exists() and products_cache.stat().st_size > 0:
                self._load_products_cache(products_cache)
            
            self._loaded = True
            logger.info(f"인메모리 그래프 로드 완료: {self.get_status()}")
            return True
            
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"인메모리 그래프 로드 실패: {e}")
            return False
    
    def _load_users(self, path: Path) -> None:
        """사용자 CSV 로드."""
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get("user_id", "")
                if not cid:
                    continue
                
                customer = CustomerData(
                    customer_id=cid,
                    name=row.get("name", ""),
                    email=row.get("email", ""),
                    segment=row.get("membership_level", "Regular"),
                )
                self._customers[cid] = customer
                self._graph.add_node(
                    f"customer:{cid}",
                    type="customer",
                    **customer.__dict__,
                )
        
        logger.info(f"사용자 {len(self._customers)}명 로드됨")
    
    def _load_orders_and_products(self, orders_path: Path, items_path: Path) -> None:
        """주문 및 상품 로드."""
        # 주문 정보 로드
        orders_map: Dict[str, Dict[str, Any]] = {}
        with open(orders_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                orders_map[row.get("order_id", "")] = row
        
        # 주문 아이템에서 상품 및 구매 관계 생성
        product_purchases: Dict[str, List[str]] = defaultdict(list)  # product_id -> [customer_ids]
        
        with open(items_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                order_id = row.get("order_id", "")
                product_id = row.get("product_id", "")
                
                if not order_id or not product_id:
                    continue
                
                order = orders_map.get(order_id, {})
                customer_id = order.get("user_id", "")
                
                # 상품 노드 생성 (없으면)
                if product_id not in self._products:
                    price = float(row.get("unit_price", 0))
                    # 카테고리 추정 (상품 ID prefix)
                    category = self._guess_category(product_id)
                    
                    product = ProductData(
                        product_id=product_id,
                        name=f"상품 {product_id}",
                        price=price,
                        category_id=category,
                        avg_rating=4.0 + (hash(product_id) % 10) / 10,  # 4.0~4.9
                        review_count=(hash(product_id) % 500) + 10,
                    )
                    self._products[product_id] = product
                    self._categories.add(category)
                    
                    self._graph.add_node(
                        f"product:{product_id}",
                        type="product",
                        **product.__dict__,
                    )
                
                # 구매 관계 생성
                if customer_id and customer_id in self._customers:
                    product_purchases[product_id].append(customer_id)
                    
                    self._graph.add_edge(
                        f"customer:{customer_id}",
                        f"product:{product_id}",
                        type="purchased",
                        order_id=order_id,
                        purchased_at=order.get("order_date", ""),
                        quantity=int(row.get("quantity", 1)),
                        unit_price=float(row.get("unit_price", 0)),
                    )
        
        # 함께 구매된 상품 관계 (같은 고객이 구매한 상품들)
        for pid, customers in product_purchases.items():
            customer_set = set(customers)
            for other_pid, other_customers in product_purchases.items():
                if pid >= other_pid:  # 중복 방지
                    continue
                common = customer_set & set(other_customers)
                if len(common) >= 2:  # 최소 2명 이상 공통 구매
                    self._graph.add_edge(
                        f"product:{pid}",
                        f"product:{other_pid}",
                        type="bought_together",
                        frequency=len(common),
                    )
        
        logger.info(f"상품 {len(self._products)}개, 카테고리 {len(self._categories)}개 생성됨")
    
    def _load_products_cache(self, path: Path) -> None:
        """상품 캐시 로드."""
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get("product_id", row.get("asin", ""))
                if not pid:
                    continue
                
                product = ProductData(
                    product_id=pid,
                    name=row.get("title", row.get("name", f"상품 {pid}")),
                    price=float(row.get("price", 0)),
                    category_id=row.get("category", row.get("main_category", "")),
                    brand=row.get("brand", ""),
                    avg_rating=float(row.get("avg_rating", row.get("average_rating", 4.0))),
                    review_count=int(row.get("review_count", row.get("rating_number", 0))),
                )
                self._products[pid] = product
                
                if product.category_id:
                    self._categories.add(product.category_id)
                
                self._graph.add_node(
                    f"product:{pid}",
                    type="product",
                    **product.__dict__,
                )
        
        self._create_category_nodes()
    
    def _create_category_nodes(self) -> None:
        """카테고리 노드 및 IN_CATEGORY 엣지 생성."""
        for cat in self._categories:
            if not cat:
                continue
            cat_node = f"category:{cat}"
            if cat_node not in self._graph:
                self._graph.add_node(
                    cat_node,
                    type="category",
                    category_id=cat,
                    name=cat,
                )
        
        for pid, product in self._products.items():
            if product.category_id:
                self._graph.add_edge(
                    f"product:{pid}",
                    f"category:{product.category_id}",
                    type="in_category",
                )
        
        logger.info(f"카테고리 노드 {len(self._categories)}개 생성됨")
    
    def _guess_category(self, product_id: str) -> str:
        """상품 ID로 카테고리 추정."""
        # Amazon ASIN 패턴 분석
        if product_id.startswith("B0"):
            prefix = product_id[:4]
            categories = {
                "B000": "Electronics",
                "B001": "Home & Kitchen",
                "B002": "Sports",
                "B003": "Books",
                "B004": "Toys",
                "B005": "Beauty",
                "B006": "Fashion",
                "B007": "Automotive",
                "B008": "Garden",
                "B009": "Office",
                "B00C": "Electronics",
                "B00D": "Home & Kitchen",
                "B00S": "Sports",
                "B076": "Electronics",
                "B0C8": "Electronics",
            }
            return categories.get(prefix, "General")
        return "General"
    
    # ============================================
    # 추천 쿼리 (GraphRepository 호환)
    # ============================================
    
    def get_similar_products(
        self,
        product_id: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """유사 상품 추천."""
        if not self.is_available():
            return []
        
        if product_id not in self._products:
            return []
        
        base = self._products[product_id]
        results = []
        
        for pid, prod in self._products.items():
            if pid == product_id:
                continue
            
            # 유사도 점수 계산
            score = 0.0
            
            # 같은 카테고리
            if prod.category_id == base.category_id:
                score += 0.4
            
            # 같은 브랜드
            if prod.brand and prod.brand == base.brand:
                score += 0.2
            
            # 가격대 유사 (30% 이내)
            if base.price > 0:
                price_diff = abs(prod.price - base.price) / base.price
                if price_diff < 0.3:
                    score += 0.2 * (1 - price_diff)
            
            # 평점 유사
            rating_diff = abs(prod.avg_rating - base.avg_rating)
            if rating_diff < 1.0:
                score += 0.2 * (1 - rating_diff)
            
            if score > 0:
                results.append({
                    "product_id": pid,
                    "name": prod.name,
                    "price": prod.price,
                    "score": round(score, 3),
                    "reason": "이 상품과 유사한 상품입니다",
                    "category_id": prod.category_id,
                    "brand": prod.brand,
                    "avg_rating": prod.avg_rating,
                })
        
        # 점수순 정렬
        results.sort(key=lambda x: (-x["score"], -x.get("avg_rating", 0)))
        return results[:top_k]
    
    def get_personalized_recommendations(
        self,
        customer_id: str,
        top_k: int = 10,
        exclude_purchased: bool = True,
    ) -> List[Dict[str, Any]]:
        """개인화 추천 (협업 필터링)."""
        if not self.is_available():
            return []
        
        customer_node = f"customer:{customer_id}"
        if customer_node not in self._graph:
            return []
        
        # 이 고객이 구매한 상품
        purchased = set()
        for _, target, data in self._graph.out_edges(customer_node, data=True):
            if data.get("type") == "purchased":
                purchased.add(target.replace("product:", ""))
        
        # 비슷한 고객 찾기 (공통 구매 상품이 많은 고객)
        similar_customers: Dict[str, int] = defaultdict(int)
        
        for pid in purchased:
            product_node = f"product:{pid}"
            # 이 상품을 구매한 다른 고객
            for source, _, data in self._graph.in_edges(product_node, data=True):
                if data.get("type") == "purchased" and source != customer_node:
                    cid = source.replace("customer:", "")
                    similar_customers[cid] += 1
        
        # 유사 고객 상위 50명
        top_similar = sorted(similar_customers.items(), key=lambda x: -x[1])[:50]
        
        # 유사 고객들이 구매한 상품 집계
        recommendations: Dict[str, float] = defaultdict(float)
        
        for similar_cid, common_count in top_similar:
            similar_node = f"customer:{similar_cid}"
            for _, target, data in self._graph.out_edges(similar_node, data=True):
                if data.get("type") == "purchased":
                    pid = target.replace("product:", "")
                    if exclude_purchased and pid in purchased:
                        continue
                    recommendations[pid] += common_count
        
        # 결과 생성
        results = []
        for pid, score in sorted(recommendations.items(), key=lambda x: -x[1])[:top_k]:
            prod = self._products.get(pid)
            if prod:
                results.append({
                    "product_id": pid,
                    "name": prod.name,
                    "price": prod.price,
                    "score": round(score, 1),
                    "reason": "비슷한 취향의 고객이 구매한 상품입니다",
                    "category_id": prod.category_id,
                    "brand": prod.brand,
                    "avg_rating": prod.avg_rating,
                })
        
        return results
    
    def get_bought_together(
        self,
        product_id: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """함께 구매한 상품."""
        if not self.is_available():
            return []
        
        product_node = f"product:{product_id}"
        if product_node not in self._graph:
            return []
        
        # bought_together 관계 조회
        results = []
        
        for _, target, data in self._graph.out_edges(product_node, data=True):
            if data.get("type") == "bought_together":
                pid = target.replace("product:", "")
                prod = self._products.get(pid)
                if prod:
                    results.append({
                        "product_id": pid,
                        "name": prod.name,
                        "price": prod.price,
                        "score": float(data.get("frequency", 1)),
                        "reason": "이 상품과 함께 구매하면 좋은 상품입니다",
                        "category_id": prod.category_id,
                        "brand": prod.brand,
                        "avg_rating": prod.avg_rating,
                    })
        
        # 역방향도 체크
        for source, _, data in self._graph.in_edges(product_node, data=True):
            if data.get("type") == "bought_together":
                pid = source.replace("product:", "")
                if any(r["product_id"] == pid for r in results):
                    continue
                prod = self._products.get(pid)
                if prod:
                    results.append({
                        "product_id": pid,
                        "name": prod.name,
                        "price": prod.price,
                        "score": float(data.get("frequency", 1)),
                        "reason": "이 상품과 함께 구매하면 좋은 상품입니다",
                        "category_id": prod.category_id,
                        "brand": prod.brand,
                        "avg_rating": prod.avg_rating,
                    })
        
        results.sort(key=lambda x: -x["score"])
        return results[:top_k]
    
    def get_trending_products(
        self,
        period_days: int = 7,
        category_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """인기 상품."""
        if not self.is_available():
            return []
        
        # 구매 빈도 집계
        purchase_counts: Dict[str, int] = defaultdict(int)
        
        for source, target, data in self._graph.edges(data=True):
            if data.get("type") == "purchased":
                pid = target.replace("product:", "")
                purchase_counts[pid] += data.get("quantity", 1)
        
        # 결과 생성
        results = []
        for pid, count in purchase_counts.items():
            prod = self._products.get(pid)
            if not prod:
                continue
            
            if category_id and prod.category_id != category_id:
                continue
            
            # 인기 점수: 구매 수 + 평점 가중치
            score = count * 0.7 + prod.avg_rating * 0.3
            
            results.append({
                "product_id": pid,
                "name": prod.name,
                "price": prod.price,
                "score": round(score, 2),
                "reason": f"{count}명이 구매한 인기 상품입니다",
                "category_id": prod.category_id,
                "brand": prod.brand,
                "avg_rating": prod.avg_rating,
            })
        
        results.sort(key=lambda x: -x["score"])
        return results[:top_k]
    
    def get_category_recommendations(
        self,
        category_id: str,
        top_k: int = 10,
        min_rating: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """카테고리별 추천."""
        if not self.is_available():
            return []
        
        results = []
        for pid, prod in self._products.items():
            if prod.category_id != category_id:
                continue
            if prod.avg_rating < min_rating:
                continue
            
            results.append({
                "product_id": pid,
                "name": prod.name,
                "price": prod.price,
                "score": prod.avg_rating,
                "reason": "이 카테고리의 인기 상품입니다",
                "category_id": prod.category_id,
                "brand": prod.brand,
                "avg_rating": prod.avg_rating,
            })
        
        results.sort(key=lambda x: -x["score"])
        return results[:top_k]
    
    def get_stats(self) -> Dict[str, int]:
        """통계."""
        if not self.is_available():
            return {}
        
        purchases = sum(
            1 for _, _, d in self._graph.edges(data=True)
            if d.get("type") == "purchased"
        )
        
        return {
            "products": len(self._products),
            "customers": len(self._customers),
            "categories": len(self._categories),
            "purchases": purchases,
        }


# 편의 함수
def get_inmemory_graph() -> InMemoryGraph:
    """인메모리 그래프 인스턴스."""
    return InMemoryGraph.get_instance()


def is_inmemory_available() -> bool:
    """인메모리 그래프 사용 가능 여부."""
    return get_inmemory_graph().is_available()
