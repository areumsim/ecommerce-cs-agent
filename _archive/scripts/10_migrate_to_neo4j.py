#!/usr/bin/env python3
"""Neo4j 데이터 마이그레이션 스크립트.

products.parquet, users.csv, orders.csv → Neo4j 그래프 DB

사용법:
    python scripts/10_migrate_to_neo4j.py [--dry-run] [--batch-size 1000]

환경변수:
    NEO4J_URI: Neo4j Bolt URI (기본: bolt://localhost:7687)
    NEO4J_USER: 사용자명 (기본: neo4j)
    NEO4J_PASSWORD: 비밀번호 (필수)
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Parquet 지원 (선택적)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas 미설치 - parquet 파일 로드 불가")


def load_config() -> Dict[str, Any]:
    """설정 로드."""
    config_path = Path("configs/neo4j.yaml")
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def iter_csv(path: Path, batch_size: int = 1000) -> Generator[List[Dict[str, Any]], None, None]:
    """CSV 파일을 배치로 읽기."""
    if not path.exists():
        logger.warning(f"파일 없음: {path}")
        return
    
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def iter_parquet(path: Path, batch_size: int = 1000) -> Generator[List[Dict[str, Any]], None, None]:
    """Parquet 파일을 배치로 읽기."""
    if not HAS_PANDAS:
        logger.error("pandas 필요: pip install pandas pyarrow")
        return
    
    if not path.exists():
        logger.warning(f"파일 없음: {path}")
        return
    
    try:
        df = pd.read_parquet(path)
        for start in range(0, len(df), batch_size):
            end = min(start + batch_size, len(df))
            batch = df.iloc[start:end].to_dict("records")
            yield batch
    except Exception as e:
        logger.error(f"Parquet 로드 실패: {e}")


class Neo4jMigrator:
    """Neo4j 마이그레이션 도구."""
    
    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        batch_size: int = 1000,
        dry_run: bool = False,
    ):
        """초기화."""
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.batch_size = batch_size
        self.dry_run = dry_run
        
        self._driver = None
        self._stats = {
            "products": 0,
            "customers": 0,
            "categories": 0,
            "purchases": 0,
            "errors": 0,
        }
    
    def connect(self) -> bool:
        """Neo4j 연결."""
        if self.dry_run:
            logger.info("[DRY-RUN] Neo4j 연결 스킵")
            return True
        
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            self._driver.verify_connectivity()
            logger.info(f"Neo4j 연결 성공: {self.uri}")
            return True
        except ImportError:
            logger.error("neo4j 패키지 필요: pip install neo4j")
            return False
        except Exception as e:
            logger.error(f"Neo4j 연결 실패: {e}")
            return False
    
    def close(self):
        """연결 종료."""
        if self._driver:
            self._driver.close()
    
    def _execute_batch(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """배치 쿼리 실행."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] 배치 실행: {len(params_list)}건")
            return len(params_list)
        
        if not self._driver:
            return 0
        
        count = 0
        with self._driver.session(database=self.database) as session:
            try:
                result = session.run(query, {"batch": params_list})
                summary = result.consume()
                count = summary.counters.nodes_created + summary.counters.relationships_created
            except Exception as e:
                logger.error(f"쿼리 실행 실패: {e}")
                self._stats["errors"] += 1
        return count
    
    def create_constraints(self):
        """제약조건 및 인덱스 생성."""
        constraints = [
            "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
            "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE",
            "CREATE CONSTRAINT category_id IF NOT EXISTS FOR (cat:Category) REQUIRE cat.category_id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX product_category IF NOT EXISTS FOR (p:Product) ON (p.category_id)",
            "CREATE INDEX product_brand IF NOT EXISTS FOR (p:Product) ON (p.brand)",
            "CREATE INDEX product_rating IF NOT EXISTS FOR (p:Product) ON (p.avg_rating)",
        ]
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] 제약조건 {len(constraints)}개, 인덱스 {len(indexes)}개 생성 예정")
            return
        
        if not self._driver:
            return
        
        with self._driver.session(database=self.database) as session:
            for stmt in constraints + indexes:
                try:
                    session.run(stmt)
                    logger.debug(f"실행: {stmt[:60]}...")
                except Exception as e:
                    logger.warning(f"스키마 생성 실패 (이미 존재할 수 있음): {e}")
        
        logger.info("스키마 생성 완료")
    
    def migrate_products(self, source_path: Path):
        """상품 마이그레이션."""
        logger.info(f"상품 마이그레이션 시작: {source_path}")
        
        query = """
        UNWIND $batch AS prod
        MERGE (p:Product {product_id: prod.product_id})
        SET p.name = prod.name,
            p.price = toFloat(prod.price),
            p.category_id = prod.category_id,
            p.brand = prod.brand,
            p.avg_rating = toFloat(prod.avg_rating),
            p.review_count = toInteger(prod.review_count),
            p.stock_status = coalesce(prod.stock_status, 'in_stock'),
            p.updated_at = datetime()
        """
        
        # 파일 형식에 따라 로더 선택
        if source_path.suffix == ".parquet":
            iterator = iter_parquet(source_path, self.batch_size)
        else:
            iterator = iter_csv(source_path, self.batch_size)
        
        total = 0
        for batch in iterator:
            # 필드 정규화
            normalized = []
            for row in batch:
                normalized.append({
                    "product_id": str(row.get("product_id", row.get("asin", ""))),
                    "name": str(row.get("title", row.get("name", ""))),
                    "price": row.get("price", 0),
                    "category_id": str(row.get("category", row.get("category_id", row.get("main_category", "")))),
                    "brand": str(row.get("brand", "")),
                    "avg_rating": row.get("avg_rating", row.get("average_rating", 0)),
                    "review_count": row.get("review_count", row.get("rating_number", 0)),
                    "stock_status": row.get("stock_status", "in_stock"),
                })
            
            count = self._execute_batch(query, normalized)
            total += len(normalized)
            logger.info(f"상품 {total}건 처리됨")
        
        self._stats["products"] = total
        logger.info(f"상품 마이그레이션 완료: {total}건")
    
    def migrate_customers(self, source_path: Path):
        """고객 마이그레이션."""
        logger.info(f"고객 마이그레이션 시작: {source_path}")
        
        query = """
        UNWIND $batch AS cust
        MERGE (c:Customer {customer_id: cust.customer_id})
        SET c.email = cust.email,
            c.name = cust.name,
            c.segment = coalesce(cust.segment, 'Regular'),
            c.created_at = cust.created_at,
            c.updated_at = datetime()
        """
        
        total = 0
        for batch in iter_csv(source_path, self.batch_size):
            normalized = []
            for row in batch:
                normalized.append({
                    "customer_id": str(row.get("user_id", "")),
                    "email": str(row.get("email", "")),
                    "name": str(row.get("name", "")),
                    "segment": row.get("segment", "Regular"),
                    "created_at": row.get("created_at", datetime.now().isoformat()),
                })
            
            count = self._execute_batch(query, normalized)
            total += len(normalized)
            logger.info(f"고객 {total}건 처리됨")
        
        self._stats["customers"] = total
        logger.info(f"고객 마이그레이션 완료: {total}건")
    
    def migrate_purchases(self, orders_path: Path, items_path: Path):
        """구매 관계 마이그레이션."""
        logger.info(f"구매 관계 마이그레이션 시작")
        
        # 주문 정보 로드
        orders_map: Dict[str, Dict[str, Any]] = {}
        for batch in iter_csv(orders_path, self.batch_size):
            for row in batch:
                orders_map[row.get("order_id", "")] = row
        
        logger.info(f"주문 {len(orders_map)}건 로드됨")
        
        # 주문 아이템으로 PURCHASED 관계 생성
        query = """
        UNWIND $batch AS item
        MATCH (c:Customer {customer_id: item.customer_id})
        MATCH (p:Product {product_id: item.product_id})
        MERGE (c)-[r:PURCHASED {order_id: item.order_id}]->(p)
        SET r.purchased_at = datetime(item.purchased_at),
            r.quantity = toInteger(item.quantity),
            r.unit_price = toFloat(item.unit_price)
        """
        
        total = 0
        for batch in iter_csv(items_path, self.batch_size):
            normalized = []
            for row in batch:
                order_id = row.get("order_id", "")
                order = orders_map.get(order_id, {})
                
                normalized.append({
                    "customer_id": order.get("user_id", ""),
                    "product_id": str(row.get("product_id", "")),
                    "order_id": order_id,
                    "purchased_at": order.get("order_date", datetime.now().isoformat()),
                    "quantity": row.get("quantity", 1),
                    "unit_price": row.get("unit_price", 0),
                })
            
            # customer_id가 있는 것만 필터
            normalized = [n for n in normalized if n["customer_id"]]
            
            if normalized:
                count = self._execute_batch(query, normalized)
                total += len(normalized)
                logger.info(f"구매 관계 {total}건 처리됨")
        
        self._stats["purchases"] = total
        logger.info(f"구매 관계 마이그레이션 완료: {total}건")
    
    def migrate_categories(self):
        """카테고리 노드 생성 (상품에서 추출)."""
        if self.dry_run:
            logger.info("[DRY-RUN] 카테고리 추출 스킵")
            return
        
        if not self._driver:
            return
        
        query = """
        MATCH (p:Product)
        WHERE p.category_id IS NOT NULL AND p.category_id <> ''
        WITH DISTINCT p.category_id AS category_id
        MERGE (cat:Category {category_id: category_id})
        SET cat.name = category_id,
            cat.level = 0
        RETURN count(cat) AS count
        """
        
        with self._driver.session(database=self.database) as session:
            result = session.run(query)
            record = result.single()
            count = record["count"] if record else 0
            self._stats["categories"] = count
            logger.info(f"카테고리 {count}개 생성됨")
        
        # 상품-카테고리 관계 생성
        rel_query = """
        MATCH (p:Product)
        WHERE p.category_id IS NOT NULL AND p.category_id <> ''
        MATCH (cat:Category {category_id: p.category_id})
        MERGE (p)-[:BELONGS_TO]->(cat)
        """
        with self._driver.session(database=self.database) as session:
            session.run(rel_query)
            logger.info("상품-카테고리 관계 생성됨")
    
    def get_stats(self) -> Dict[str, int]:
        """마이그레이션 통계."""
        return self._stats


def main():
    """메인 함수."""
    parser = argparse.ArgumentParser(description="Neo4j 데이터 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="실제 실행 없이 검증만")
    parser.add_argument("--batch-size", type=int, default=1000, help="배치 크기")
    parser.add_argument("--products", type=str, help="상품 데이터 경로 (parquet/csv)")
    parser.add_argument("--users", type=str, help="사용자 데이터 경로 (csv)")
    parser.add_argument("--orders", type=str, help="주문 데이터 경로 (csv)")
    parser.add_argument("--order-items", type=str, help="주문 아이템 데이터 경로 (csv)")
    args = parser.parse_args()
    
    # 설정 로드
    config = load_config()
    neo4j_cfg = config.get("neo4j", {})
    migration_cfg = config.get("migration", {})
    sources = migration_cfg.get("sources", {})
    
    # 환경변수/설정 병합
    uri = os.environ.get("NEO4J_URI", neo4j_cfg.get("uri", "bolt://localhost:7687"))
    user = os.environ.get("NEO4J_USER", neo4j_cfg.get("user", "neo4j"))
    password = os.environ.get("NEO4J_PASSWORD", neo4j_cfg.get("password", ""))
    database = os.environ.get("NEO4J_DATABASE", neo4j_cfg.get("database", "neo4j"))
    
    if not password and not args.dry_run:
        logger.error("NEO4J_PASSWORD 환경변수 필요")
        sys.exit(1)
    
    # 데이터 소스 경로
    products_path = Path(args.products or sources.get("products", "data/mock_csv/products_cache.csv"))
    users_path = Path(args.users or sources.get("users", "data/mock_csv/users.csv"))
    orders_path = Path(args.orders or sources.get("orders", "data/mock_csv/orders.csv"))
    items_path = Path(args.order_items or sources.get("order_items", "data/mock_csv/order_items.csv"))
    
    # 마이그레이터 생성
    migrator = Neo4jMigrator(
        uri=uri,
        user=user,
        password=password,
        database=database,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    
    try:
        # 연결
        if not migrator.connect():
            sys.exit(1)
        
        # 스키마 생성
        migrator.create_constraints()
        
        # 마이그레이션 실행
        migrator.migrate_products(products_path)
        migrator.migrate_customers(users_path)
        migrator.migrate_purchases(orders_path, items_path)
        migrator.migrate_categories()
        
        # 통계 출력
        stats = migrator.get_stats()
        logger.info("=" * 50)
        logger.info("마이그레이션 완료 통계:")
        logger.info(f"  상품: {stats['products']}건")
        logger.info(f"  고객: {stats['customers']}건")
        logger.info(f"  카테고리: {stats['categories']}건")
        logger.info(f"  구매 관계: {stats['purchases']}건")
        logger.info(f"  오류: {stats['errors']}건")
        logger.info("=" * 50)
        
    finally:
        migrator.close()


if __name__ == "__main__":
    main()
