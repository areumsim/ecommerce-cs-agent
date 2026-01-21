# Graph-Based Recommendation System - Technical Documentation

## Overview

이 문서는 이커머스 CS 에이전트의 그래프 기반 추천 시스템의 기술적 구현, 이론적 배경, 유사 기술 비교를 다룹니다.

---

## 0. 핵심 설계 결정

### 0.1 왜 Neo4j인가?

#### 그래프 DB vs 관계형 DB

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    "user_001이 구매한 상품과 비슷한 상품 찾기"                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [관계형 DB - SQL]                                                           │
│  SELECT p2.*                                                                 │
│  FROM orders o1                                                              │
│  JOIN order_items oi1 ON o1.order_id = oi1.order_id                         │
│  JOIN products p1 ON oi1.product_id = p1.product_id                         │
│  JOIN products p2 ON p1.category_id = p2.category_id                        │
│  WHERE o1.user_id = 'user_001'                                              │
│    AND p2.product_id != p1.product_id                                       │
│  GROUP BY p2.product_id                                                      │
│  ORDER BY COUNT(*) DESC;                                                     │
│                                                                              │
│  → 복잡한 JOIN, 성능 저하, 가독성 낮음                                       │
│                                                                              │
│  [그래프 DB - Cypher]                                                        │
│  MATCH (c:Customer {id: 'user_001'})-[:PURCHASED]->(p:Product)              │
│        -[:SIMILAR_TO]->(rec:Product)                                        │
│  RETURN rec                                                                  │
│                                                                              │
│  → 직관적, 관계 탐색 최적화, 확장 용이                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Neo4j 선택 이유

| 기준 | Neo4j | 대안들 |
|------|-------|--------|
| **관계 중심 쿼리** | O(1) 관계 탐색 | SQL: O(n) JOIN |
| **Cypher 언어** | 선언적, 직관적 | SQL: 복잡한 서브쿼리 |
| **ACID 트랜잭션** | 지원 | 일부 그래프 DB 미지원 |
| **커뮤니티/문서** | 풍부 | 상대적으로 부족 |
| **Python 드라이버** | 공식 지원 | 비공식/미성숙 |

#### Neo4j 동작 원리

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Neo4j 내부 구조                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. 네이티브 그래프 저장소 (Index-Free Adjacency)                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  일반 DB:  노드 → 인덱스 조회 → 연결 노드 찾기 (O(log n))            │   │
│  │  Neo4j:    노드 → 포인터로 직접 연결 노드 접근 (O(1))                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  2. 저장 구조                                                                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │ Node Store  │     │Relationship │     │ Property    │                   │
│  │             │────▶│   Store     │────▶│   Store     │                   │
│  │ (노드 ID,   │     │ (시작/끝   │     │ (키-값     │                   │
│  │  첫 관계    │     │  노드 ID,  │     │  속성)     │                   │
│  │  포인터)    │     │  다음 관계 │     │             │                   │
│  └─────────────┘     │  포인터)   │     └─────────────┘                   │
│                      └─────────────┘                                        │
│                                                                              │
│  3. 쿼리 실행                                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Cypher → Parser → Planner → Optimizer → Executor → Result          │   │
│  │                                                                      │   │
│  │  MATCH (a)-[:KNOWS]->(b)                                            │   │
│  │     ↓                                                                │   │
│  │  1. a 노드 찾기 (인덱스/스캔)                                        │   │
│  │  2. a의 KNOWS 관계 포인터 따라가기                                   │   │
│  │  3. b 노드 반환                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 0.2 RDF/SPARQL 온톨로지 적용

> **Note**: 이 프로젝트는 RDFLib 기반 OWL 온톨로지와 SPARQL 쿼리를 적용했습니다.

#### 구현된 온톨로지 구조

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    이커머스 온톨로지 (ontology/ecommerce.ttl)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  클래스 계층 (OWL):                                                          │
│  ┌─────────────┐                                                            │
│  │ owl:Thing   │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                    │
│    ┌────┴────┬────────────┬────────────┐                                   │
│    ▼         ▼            ▼            ▼                                   │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐                             │
│ │Customer│ │Product │ │ Order  │ │ Category │                             │
│ │(Person)│ │        │ │        │ │          │                             │
│ └────────┘ └────────┘ └────────┘ └────┬─────┘                             │
│                                       │                                     │
│                              ┌────────┼────────┐                           │
│                              ▼        ▼        ▼                           │
│                         Electronics  Audio  Accessories                     │
│                                                                              │
│  ObjectProperty (관계):                                                      │
│  - ecom:purchased    (Customer → Product)                                   │
│  - ecom:placedOrder  (Customer → Order)                                     │
│  - ecom:similarTo    (Product ↔ Product, SymmetricProperty)                │
│  - ecom:inCategory   (Product → Category)                                   │
│                                                                              │
│  DatatypeProperty (속성):                                                    │
│  - ecom:customerId, ecom:email, ecom:membershipLevel                        │
│  - ecom:productId, ecom:title, ecom:price, ecom:averageRating              │
│  - ecom:embedding (xsd:base64Binary - 384차원 벡터)                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 기술 스택 비교

| 측면 | 이 프로젝트 (RDFLib) | Neo4j | Fuseki |
|------|---------------------|-------|--------|
| **온톨로지** | OWL (ecommerce.ttl) | 스키마리스 | OWL/RDFS |
| **쿼리 언어** | SPARQL | Cypher | SPARQL |
| **저장소** | 인메모리 (RDFLib) | 디스크 기반 | TDB2 |
| **추론** | 미사용 (쿼리로 해결) | 미지원 | Jena Reasoner |
| **벡터 검색** | NumPy (base64 임베딩) | 미지원 | 미지원 |
| **설치** | pip install rdflib | Docker/설치 | Docker/설치 |
| **트리플 수** | ~10K 적합 | ~수백만 | ~수억 |

#### 왜 RDFLib를 선택했는가?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      의사결정: RDFLib 선택 이유                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. 외부 의존성 없음                                                         │
│     - pip install rdflib 만으로 완료                                         │
│     - Docker, 별도 서버 불필요                                               │
│     - CI/CD 파이프라인 단순화                                                │
│                                                                              │
│  2. PoC 규모에 적합                                                          │
│     - 8,779 트리플 (고객 100, 상품 100, 주문 100)                            │
│     - 인메모리로 충분한 성능                                                 │
│     - 초기 로드 < 1초                                                        │
│                                                                              │
│  3. 표준 SPARQL 지원                                                         │
│     - 협업 필터링, 유사 상품 등 복잡한 쿼리 가능                             │
│     - 향후 Fuseki/Virtuoso로 마이그레이션 용이                               │
│     - 동일한 TTL 파일 재사용                                                 │
│                                                                              │
│  4. 벡터 검색 통합                                                           │
│     - 임베딩을 base64로 트리플에 저장                                        │
│     - NumPy로 코사인 유사도 계산                                             │
│     - SPARQL + 벡터 하이브리드 검색                                          │
│                                                                              │
│  결론: PoC 목적으로 RDFLib가 최적, 대규모 시 Fuseki로 전환                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 향후 확장: Apache Jena Fuseki

```
현재 (RDFLib 인메모리):                  확장 시 (Fuseki):
┌──────────────────┐                   ┌──────────────────┐
│  Python App      │                   │  Python App      │
│  ┌────────────┐  │                   │                  │
│  │ RDFLib     │  │                   │  HTTP Client     │
│  │ Graph      │  │        →          │                  │
│  └────────────┘  │                   └────────┬─────────┘
│  ontology/*.ttl  │                            │
└──────────────────┘                            ▼
                                       ┌──────────────────┐
                                       │  Fuseki Server   │
                                       │  ┌────────────┐  │
                                       │  │ TDB2       │  │
                                       │  │ (디스크)   │  │
                                       │  └────────────┘  │
                                       │  ontology/*.ttl  │  ← 동일 파일
                                       │  SPARQL Endpoint │
                                       └──────────────────┘

마이그레이션 단계:
1. 동일한 TTL 파일을 Fuseki에 로드
2. SPARQL 엔드포인트 URL만 변경
3. 수억 트리플까지 확장 가능
```

#### SPARQL 쿼리 예제 (협업 필터링)

```sparql
SELECT ?productId ?title ?price (COUNT(?otherCustomer) as ?score)
WHERE {
    ?me a ecom:Customer ;
        ecom:customerId "user_001" ;
        ecom:purchased ?commonProduct .
    
    ?otherCustomer a ecom:Customer ;
                   ecom:purchased ?commonProduct ;
                   ecom:purchased ?product .
    
    FILTER(?otherCustomer != ?me)
    FILTER NOT EXISTS { ?me ecom:purchased ?product }
    
    ?product ecom:productId ?productId ;
             ecom:title ?title ;
             ecom:price ?price .
}
GROUP BY ?productId ?title ?price
ORDER BY DESC(?score)
LIMIT 10
```

#### 온톨로지 확장이 유리한 시나리오

```
1. 복잡한 추론이 필요한 경우
   - "비건 고객에게 동물성 원료 없는 화장품 추천"
   - 제품 성분 → 원료 출처 → 비건 여부 추론 체인
   - 현재: SPARQL 쿼리로 명시적 관계만 탐색
   - 확장: Jena Reasoner로 자동 추론

2. 외부 지식그래프 연동
   - Wikidata, DBpedia와 연결
   - 시맨틱 매핑 (owl:sameAs)

3. 대규모 데이터
   - 수백만 트리플 이상
   - Fuseki + TDB2로 마이그레이션
```

---

## 1. System Architecture

### 현재 구현 (실제 사용 중)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐       │
│   │      Gradio UI (ui.py)      │    │   FastAPI (api.py)          │       │
│   └──────────────┬──────────────┘    └──────────────┬──────────────┘       │
│                  │                                   │                       │
│                  ▼                                   ▼                       │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐       │
│   │      RDFRepository          │    │  RecommendationService      │       │
│   │      (src/rdf/)             │    │  (src/recommendation/)      │       │
│   │  ✅ 사용 중                 │    │                             │       │
│   └──────────────┬──────────────┘    └──────────────┬──────────────┘       │
│                  │                                   │                       │
│                  ▼                                   ▼                       │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐       │
│   │      RDFLib (SPARQL)        │    │      NetworkX (인메모리)     │       │
│   │  ✅ 사용 중                 │    │  ✅ 사용 중 (폴백)          │       │
│   └──────────────┬──────────────┘    └──────────────┬──────────────┘       │
│                  │                                   │                       │
│                  ▼                                   ▼                       │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐       │
│   │      ontology/*.ttl         │    │      data/mock_csv/         │       │
│   │      (8,779 트리플)          │    │      (CSV 데이터)           │       │
│   └─────────────────────────────┘    └─────────────────────────────┘       │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                    ❌ Neo4j (미사용)                             │      │
│   │   설정: configs/neo4j.yaml 존재                                  │      │
│   │   코드: src/graph/repository.py 구현됨                           │      │
│   │   상태: 연결 안됨, 대규모 확장 시 도입 예정                       │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | File | 상태 | Role |
|-----------|------|------|------|
| **RDFRepository** | `src/rdf/repository.py` | ✅ UI 사용 | SPARQL 기반 데이터 조회, 협업 필터링 |
| **UnifiedRDFStore** | `src/rdf/store.py` | ✅ UI 사용 | RDFLib 트리플 스토어, 벡터 검색 |
| RecommendationService | `src/recommendation/service.py` | ✅ API 사용 | 추천 로직 진입점 |
| InMemoryGraph | `src/graph/inmemory.py` | ✅ API 폴백 | NetworkX 기반 그래프 연산 |
| GraphRepository | `src/graph/repository.py` | ⚠️ 구현됨 | Neo4j Cypher 쿼리 (미연결) |
| GraphConnection | `src/graph/connection.py` | ⚠️ 구현됨 | Neo4j 드라이버 관리 (미연결) |

---

## 2. Graph Data Model

### NetworkX (API 폴백 - 사용 중)

```
노드:
  customer:{user_id}  - 고객 (name, email, segment)
  product:{product_id} - 상품 (name, price, category_id, brand, avg_rating)
  category:{category_id} - 카테고리 (name)

엣지:
  PURCHASED    - 고객→상품 (order_id, purchased_at, quantity)
  SIMILAR_TO   - 상품↔상품 (score)
  IN_CATEGORY  - 상품→카테고리

현재 규모: ~1,592 노드, ~1,495 엣지
```

### Neo4j (미사용 - 확장 시 동일 스키마)

```cypher
(:Customer {customer_id, name, email, segment})
(:Product {product_id, name, price, category_id, brand, avg_rating, review_count})
(:Category {category_id, name, level})

(:Customer)-[:PURCHASED {order_id, purchased_at, quantity, unit_price}]->(:Product)
(:Product)-[:BELONGS_TO]->(:Category)
(:Product)-[:SIMILAR_TO {score, method}]-(:Product)
```

### RDF/SPARQL (Triple Store)

```turtle
# 클래스 (ontology/ecommerce.ttl)
ecom:Customer a owl:Class ; rdfs:subClassOf schema:Person .
ecom:Product a owl:Class ; rdfs:subClassOf schema:Product .
ecom:Order a owl:Class .
ecom:Category a owl:Class .

# 인스턴스 (ontology/instances/*.ttl)
ecom:customer_user_001 a ecom:Customer ;
    ecom:customerId "user_001" ;
    ecom:name "이민준" ;
    ecom:purchased ecom:product_B00004Z7D2 .

# 관계 (ObjectProperty)
ecom:purchased    rdfs:domain ecom:Customer ; rdfs:range ecom:Product .
ecom:similarTo    a owl:SymmetricProperty ; rdfs:domain ecom:Product ; rdfs:range ecom:Product .
ecom:inCategory   rdfs:domain ecom:Product ; rdfs:range ecom:Category .
```

### Example Graph

```
         ┌─────────┐
         │Customer │
         │ user_001│
         └────┬────┘
              │ PURCHASED
              ▼
         ┌─────────┐     SIMILAR_TO      ┌─────────┐
         │ Product │◄───────────────────►│ Product │
         │ PROD-01 │                     │ PROD-02 │
         └────┬────┘                     └────┬────┘
              │ BELONGS_TO                    │
              ▼                               ▼
         ┌─────────┐                    ┌─────────┐
         │Category │                    │Category │
         │Electronics│                  │Electronics│
         └─────────┘                    └─────────┘
```

---

## 3. Recommendation Algorithms

### 3.1 Content-Based Filtering (Similar Products)

**원리**: 상품 속성(카테고리, 브랜드, 가격대, 평점)의 유사성을 기반으로 추천

**Implementation**:
```python
# 유사도 점수 계산
score = 0.0
if product.category_id == base.category_id:
    score += 0.4  # 같은 카테고리
if product.brand == base.brand:
    score += 0.2  # 같은 브랜드
if abs(product.price - base.price) / base.price < 0.3:
    score += 0.2  # 가격대 유사 (30% 이내)
if abs(product.avg_rating - base.avg_rating) < 1.0:
    score += 0.2  # 평점 유사 (1점 이내)
```

**Cypher Query (Neo4j)**:
```cypher
MATCH (p:Product {product_id: $product_id})
OPTIONAL MATCH (p)-[:BELONGS_TO]->(cat:Category)<-[:BELONGS_TO]-(similar:Product)
WHERE similar.product_id <> p.product_id
WITH p, similar,
     CASE WHEN similar.category_id = p.category_id THEN 0.4 ELSE 0 END +
     CASE WHEN similar.brand = p.brand THEN 0.2 ELSE 0 END +
     CASE WHEN abs(similar.price - p.price) / p.price < 0.3 THEN 0.2 ELSE 0 END +
     CASE WHEN abs(similar.avg_rating - p.avg_rating) < 1.0 THEN 0.2 ELSE 0 END AS score
WHERE score > 0
RETURN similar.product_id, similar.name, score
ORDER BY score DESC
LIMIT $top_k
```

### 3.2 Collaborative Filtering (Personalized)

**원리**: "나와 비슷한 취향의 고객들이 구매한 상품" 추천

**Algorithm**:
1. 현재 고객이 구매한 상품 집합 P 추출
2. P의 상품을 구매한 다른 고객들 찾기 (similar customers)
3. 공통 구매 상품 수로 유사도 계산
4. 유사 고객들이 구매했지만 현재 고객이 구매하지 않은 상품 추천

**Cypher Query**:
```cypher
MATCH (me:Customer {customer_id: $customer_id})-[:PURCHASED]->(p:Product)<-[:PURCHASED]-(other:Customer)
WHERE me <> other
WITH other, COUNT(p) AS common_purchases
ORDER BY common_purchases DESC
LIMIT 50

MATCH (other)-[:PURCHASED]->(rec:Product)
WHERE NOT (me)-[:PURCHASED]->(rec)
WITH rec, COUNT(DISTINCT other) AS score
RETURN rec.product_id, rec.name, score
ORDER BY score DESC
LIMIT $top_k
```

### 3.3 Association Rules (Bought Together)

**원리**: 함께 구매된 상품 패턴 분석 (Market Basket Analysis)

**Algorithm**:
```
For each product P:
    Find all customers who purchased P
    Find all other products purchased by these customers
    Count co-occurrence frequency
    Rank by frequency
```

**Support & Confidence**:
- **Support**: P(A ∩ B) - A와 B가 함께 구매된 확률
- **Confidence**: P(B|A) - A를 구매한 고객이 B도 구매할 확률

### 3.4 Popularity-Based (Trending)

**원리**: 최근 N일간 구매 빈도가 높은 상품

**Score Calculation**:
```
trending_score = purchase_count * 0.7 + avg_rating * 0.3
```

---

## 4. Technology Comparison

### 4.1 Graph Databases

| Database | Strengths | Weaknesses | Use Case |
|----------|-----------|------------|----------|
| **Neo4j** | 복잡한 관계 쿼리, Cypher 언어, ACID | 비용, 운영 복잡도 | Production |
| **Amazon Neptune** | AWS 통합, 관리형 | 벤더 종속, 비용 | AWS 환경 |
| **JanusGraph** | 분산, 오픈소스 | 설정 복잡 | 대규모 |
| **NetworkX** | 단순, Python 네이티브 | 메모리 한계 | 개발/테스트 |

### 4.2 Recommendation Approaches

| Approach | Algorithm | Pros | Cons |
|----------|-----------|------|------|
| **Graph-Based** | GNN, Node2Vec | 관계 활용, 설명 가능 | 복잡도, Cold Start |
| **Matrix Factorization** | SVD, ALS | 효율적, 확장성 | 해석 어려움 |
| **Deep Learning** | NCF, Wide&Deep | 높은 정확도 | 데이터 요구량, 비용 |
| **Rule-Based** | Apriori, FP-Growth | 단순, 해석 가능 | 확장성 한계 |

### 4.3 This Project's Approach

```
┌──────────────────────────────────────────────────────────────────┐
│                    Hybrid Approach                                │
├──────────────────────────────────────────────────────────────────┤
│  Content-Based (40%) + Collaborative (60%)                       │
│                                                                   │
│  - Content: 카테고리, 브랜드, 가격대, 평점 유사도                    │
│  - Collaborative: 구매 패턴 유사 고객 기반                          │
│  - Fallback: CSV 기반 단순 매칭 (그래프 미연결 시)                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. In-Memory Graph Implementation

### 5.1 Why NetworkX?

Neo4j 서버 없이도 동작해야 하는 환경(컨테이너, 테스트, 개발)을 위해 NetworkX 기반 인메모리 그래프 구현.

**Key Features**:
- Zero external dependencies (Python only)
- Auto-load from CSV on startup
- Same interface as Neo4j repository
- Transparent fallback

### 5.2 Data Loading Flow

```
1. Application Start
      │
      ▼
2. Check Neo4j availability
      │
      ├── Available → Use Neo4j
      │
      └── Not Available
            │
            ▼
3. Load InMemoryGraph
      │
      ▼
4. Read CSV files:
   - users.csv → Customer nodes
   - orders.csv + order_items.csv → Product nodes + PURCHASED edges
      │
      ▼
5. Build derived relationships:
   - BOUGHT_TOGETHER (co-purchase frequency ≥ 2)
      │
      ▼
6. Graph Ready (1592 nodes, 1495 edges)
```

### 5.3 Performance Characteristics

| Metric | Neo4j | In-Memory (NetworkX) |
|--------|-------|----------------------|
| Startup Time | ~2s (connection) | ~0.5s (CSV load) |
| Query Latency | 10-50ms | 1-10ms |
| Memory Usage | External | ~50MB (100K nodes) |
| Scalability | Millions of nodes | ~1M nodes |
| Persistence | Disk | None (reload on restart) |

---

## 6. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/recommendations/similar/{product_id}` | GET | 유사 상품 추천 |
| `/recommendations/personalized/{user_id}` | GET | 개인화 추천 |
| `/recommendations/trending` | GET | 인기 상품 |
| `/recommendations/bought-together/{product_id}` | GET | 함께 구매 |
| `/recommendations/category/{category_id}` | GET | 카테고리별 추천 |

### Query Parameters

- `top_k`: 반환할 추천 수 (default: 10)
- `method`: 추천 방식 - `hybrid`, `collaborative`, `content` (default: hybrid)
- `period`: 인기 상품 기간 - `day`, `week`, `month` (default: week)

---

## 7. Theoretical Background

### 7.1 Graph Theory Basics

**Definitions**:
- **Node (Vertex)**: 엔티티 (고객, 상품, 카테고리)
- **Edge (Relationship)**: 노드 간 관계 (구매, 유사, 소속)
- **Degree**: 노드에 연결된 엣지 수
- **Path**: 노드 간 경로 (shortest path, all paths)

**Key Algorithms**:
- **BFS/DFS**: 그래프 탐색
- **PageRank**: 노드 중요도 계산
- **Community Detection**: 클러스터링 (Louvain, Label Propagation)
- **Node Similarity**: Jaccard, Cosine, Adamic-Adar

### 7.2 Recommendation Theory

**Cold Start Problem**:
- 새 사용자: 구매 이력 없음 → 인기 상품, 트렌딩으로 대체
- 새 상품: 구매 데이터 없음 → 컨텐츠 기반 유사도로 대체

**Evaluation Metrics**:
- **Precision@K**: 추천 중 실제 구매한 비율
- **Recall@K**: 구매 상품 중 추천된 비율
- **NDCG**: 순서 고려한 정확도
- **Hit Rate**: 추천 중 최소 1개 구매 비율

### 7.3 Hybrid Approach Benefits

```
Pure Collaborative          Pure Content-Based
     │                            │
     │  Cold Start Problem        │  Filter Bubble
     │  Sparsity Issue            │  Limited Discovery
     │                            │
     └────────────┬───────────────┘
                  │
                  ▼
            Hybrid Approach
                  │
     ┌────────────┴────────────┐
     │ - Mitigates cold start  │
     │ - Reduces filter bubble │
     │ - Better coverage       │
     │ - Explainable results   │
     └─────────────────────────┘
```

---

## 8. Similarity Graph Visualization

### 8.1 코사인 유사도 기반 시각화

상품 간 유사도는 384차원 임베딩 벡터의 **코사인 유사도**로 계산됩니다.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    코사인 유사도 계산 파이프라인                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. 임베딩 로드 (embeddings.ttl)                                             │
│     ecom:product_A ecom:embedding "base64..."^^xsd:base64Binary             │
│                                                                              │
│  2. Base64 디코딩 → NumPy float32 배열 (384차원)                             │
│     raw = base64.b64decode(emb_str)                                         │
│     vector = np.frombuffer(raw, dtype=np.float32)                           │
│                                                                              │
│  3. 코사인 유사도 계산                                                       │
│     similarity = dot(v1, v2) / (||v1|| * ||v2||)                            │
│                                                                              │
│  4. 시각화 데이터 생성                                                       │
│     {                                                                        │
│       "from": "product_A",                                                   │
│       "to": "product_B",                                                     │
│       "score": 0.903,           ← 실제 코사인 유사도                         │
│       "label": "0.90",          ← 엣지 라벨                                  │
│       "width": 4.6,             ← 점수 기반 두께 (1 + score * 4)             │
│       "color": "rgba(..., 0.94)" ← 점수 기반 투명도                          │
│     }                                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 UI 유사도 필터링

Gradio UI에서 유사도 임계값으로 필터링 가능:

| 컨트롤 | 범위 | 기본값 | 설명 |
|--------|------|--------|------|
| 표시 엣지 수 | 10-500 | 50 | 표시할 최대 엣지 수 |
| 최소 유사도 | 0.0-1.0 | 0.5 | 이 값 이상의 유사도만 표시 |

### 8.3 시각적 표현

```
유사도 점수에 따른 엣지 스타일:

  낮은 유사도 (0.5)          높은 유사도 (0.9)
        │                          │
        ▼                          ▼
  ┌─────────┐                ┌─────────┐
  │ Product │───── 0.50 ─────│ Product │    얇은 엣지, 연한 색상
  │    A    │                │    B    │
  └─────────┘                └─────────┘

  ┌─────────┐                ┌─────────┐
  │ Product │═════ 0.90 ═════│ Product │    두꺼운 엣지, 진한 색상
  │    C    │                │    D    │
  └─────────┘                └─────────┘

툴팁: "Electronics Product ↔ Electronics Product\n유사도: 0.903"
```

### 8.4 데이터 생성 스크립트

```bash
# 유사도 그래프 데이터 생성 (코사인 유사도 포함)
python scripts/export_visualization_data.py

# 출력 파일
# data/visualization/similarity_graph.json
```

**출력 예시:**
```json
{
  "nodes": [
    {"id": "B00004Z7D2", "label": "Electronics Pro", "group": "product"}
  ],
  "edges": [
    {
      "from": "B0018QIBZQ",
      "to": "B001BBIBGW",
      "label": "0.90",
      "score": 0.9027215242385864,
      "width": 4.610886096954346,
      "title": "Home & Kitchen Produ ↔ Home & Kitchen Produ\n유사도: 0.903"
    }
  ]
}
```

---

## 9. Future Improvements

### 9.1 Neo4j GDS (Graph Data Science) - 미사용, 확장 시 고려

> **현재 상태**: Neo4j 미사용. 대규모 확장 시 GDS 알고리즘 활용 가능.

```cypher
-- Node Similarity (Neo4j GDS 도입 시)
CALL gds.nodeSimilarity.stream('graph')
YIELD node1, node2, similarity
RETURN gds.util.asNode(node1).name AS p1,
       gds.util.asNode(node2).name AS p2,
       similarity
ORDER BY similarity DESC

-- PageRank for Product Importance
CALL gds.pageRank.stream('graph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS product, score
ORDER BY score DESC
```

### 9.2 Real-time Event Processing

```
User Action → Kafka → Stream Processor → Update Graph → Trigger Recommendation
```

### 9.3 A/B Testing Framework

```python
class RecommendationExperiment:
    def get_variant(self, user_id: str) -> str:
        # Hash-based consistent assignment
        return "A" if hash(user_id) % 2 == 0 else "B"
    
    def get_recommendations(self, user_id: str):
        variant = self.get_variant(user_id)
        if variant == "A":
            return self.collaborative_filtering(user_id)
        else:
            return self.hybrid_approach(user_id)
```

---

## 10. References

### Papers
- [Collaborative Filtering for Implicit Feedback Datasets](http://yifanhu.net/PUB/cf.pdf) (Hu et al., 2008)
- [Amazon.com Recommendations: Item-to-Item Collaborative Filtering](https://www.cs.umd.edu/~samir/498/Amazon-Recommendations.pdf) (Linden et al., 2003)
- [Graph Neural Networks for Social Recommendation](https://arxiv.org/abs/1902.07243) (Fan et al., 2019)

### Libraries & Tools (참조용)
- [RDFLib](https://rdflib.readthedocs.io/) - ✅ 사용 중
- [NetworkX](https://networkx.org/) - ✅ 사용 중
- [Neo4j Graph Database](https://neo4j.com/) - ❌ 미사용 (확장 시 고려)
- [PyTorch Geometric](https://pytorch-geometric.readthedocs.io/) - ❌ 미사용
- [Surprise](https://surpriselib.com/) - ❌ 미사용

### This Project
- RDF Source: `src/rdf/`, `ontology/`
- Graph Source: `src/graph/`, `src/recommendation/`
- Tests: `tests/test_rdf.py`, `tests/test_recommendation.py`
- Config: `configs/rdf.yaml`, `configs/recommendation.yaml`
