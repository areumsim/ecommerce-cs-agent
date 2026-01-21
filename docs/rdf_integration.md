# RDF/Fuseki 통합 가이드

## 개요

이 프로젝트는 **Apache Jena Fuseki** 트리플 스토어를 사용하여 모든 데이터를 관리합니다.

| 항목 | 값 |
|------|-----|
| 백엔드 | Apache Jena Fuseki 4.10.0 |
| 프로토콜 | SPARQL 1.1 over HTTP |
| 엔드포인트 | `http://ar_fuseki:3030/ecommerce` ( http://192.168.88.201:31010/#/  ) | 
| 트리플 수 | ~32,000 |
| 인증 | admin / admin123 |

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     Application                              │
│  Gradio UI (ui.py)          FastAPI (api.py)                │
└────────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                 src/rdf/store.py                             │
│  FusekiStore                                                 │
│  - SPARQL queries over HTTP                                  │
│  - UPDATE operations                                         │
│  - Vector search (embeddings)                                │
└────────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                 src/rdf/repository.py                        │
│  RDFRepository                                               │
│  - Customer CRUD                                             │
│  - Product CRUD                                              │
│  - Order/OrderItem CRUD                                      │
│  - Ticket CRUD                                               │
│  - Collaborative recommendations                             │
└────────────────────────────────┬────────────────────────────┘
                                 │ SPARQL over HTTP
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                 Apache Jena Fuseki                           │
│  http://ar_fuseki:3030/ecommerce                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  TDB2 Dataset: /ecommerce                            │   │
│  │  - OWL ontology (174 triples)                        │   │
│  │  - SHACL shapes (208 triples)                        │   │
│  │  - Instance data (~32,000 triples)                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 온톨로지 구조

### 클래스

| 클래스 | 부모 | 설명 |
|--------|------|------|
| `ecom:Customer` | schema:Person | 고객 |
| `ecom:Product` | schema:Product | 상품 |
| `ecom:Order` | - | 주문 |
| `ecom:OrderItem` | - | 주문 항목 |
| `ecom:Ticket` | - | 지원 티켓 |
| `ecom:Category` | - | 상품 카테고리 |

### 속성

| 속성 | 타입 | 도메인 → 범위 |
|------|------|---------------|
| `ecom:purchased` | ObjectProperty | Customer → Product |
| `ecom:placedOrder` | ObjectProperty | Customer → Order |
| `ecom:containsItem` | ObjectProperty | Order → OrderItem |
| `ecom:hasProduct` | ObjectProperty | OrderItem → Product |
| `ecom:similarTo` | SymmetricProperty | Product ↔ Product |
| `ecom:hasTicket` | ObjectProperty | Customer → Ticket |
| `ecom:relatedToOrder` | ObjectProperty | Ticket → Order |
| `ecom:inCategory` | ObjectProperty | Product → Category |

### 데이터 속성

| 속성 | 범위 | 설명 |
|------|------|------|
| `ecom:customerId` | xsd:string | 고객 ID (user_XXX) |
| `ecom:productId` | xsd:string | 상품 ID |
| `ecom:orderId` | xsd:string | 주문 ID (ORD_XXXXXXXX_XXXX) |
| `ecom:ticketId` | xsd:string | 티켓 ID (TICKET_XXXXXXXXXX) |
| `ecom:status` | xsd:string | 상태 |
| `ecom:price` | xsd:decimal | 가격 |
| `ecom:totalAmount` | xsd:decimal | 총액 |

## SHACL 검증

`ontology/shacl/ecommerce-shapes.ttl`에 정의된 검증 규칙:

### CustomerShape
- `customerId`: 필수, 패턴 `user_XXX`
- `email`: 필수, 이메일 형식
- `membershipLevel`: bronze/silver/gold/platinum 중 하나

### ProductShape
- `productId`: 필수
- `price`: 필수, >= 0
- `averageRating`: 0~5 범위
- `stockStatus`: in_stock/out_of_stock/limited 중 하나

### OrderShape
- `orderId`: 필수, 패턴 `ORD_XXXXXXXX_XXXX`
- `status`: pending/confirmed/shipping/delivered/cancelled 중 하나
- `orderDate`: 필수
- `totalAmount`: 필수, >= 0

### TicketShape
- `ticketId`: 필수, 패턴 `TICKET_XXXXXXXXXX`
- `issueType`: shipping/refund/exchange/product_inquiry/order_inquiry/complaint/other 중 하나
- `status`: open/in_progress/resolved/closed 중 하나
- `priority`: low/normal/high/urgent 중 하나

## 설정

### configs/rdf.yaml

```yaml
rdf:
  backend: "fuseki"  # fuseki | rdflib
fuseki:
  endpoint: "http://ar_fuseki:3030/ecommerce"
  user: "admin"
  password: "admin123"
```

## 사용법

### Python 코드

```python
from src.rdf.repository import get_rdf_repository

repo = get_rdf_repository()

# 고객 조회
customer = repo.get_customer("user_001")
print(f"이름: {customer.name}")

# 주문 조회
orders = repo.get_user_orders("user_001", limit=5)
for o in orders:
    print(f"{o.order_id}: {o.status}")

# 주문 상세
detail = repo.get_order_detail("ORD_20251219_1100")
print(f"주문 항목: {len(detail.items)}개")

# 티켓 생성
ticket = repo.create_ticket(
    user_id="user_001",
    issue_type="refund",
    description="환불 요청합니다",
    priority="high",
    order_id="ORD_20251219_1100",
)
print(f"티켓 생성: {ticket.ticket_id}")

# 협업 필터링 추천
recommendations = repo.get_collaborative_recommendations("user_001", limit=10)
for product, score in recommendations:
    print(f"{product.title}: 점수 {score}")
```

### SPARQL 쿼리 예제

```bash
# 트리플 수 확인
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'

# 엔티티 타입별 개수
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=
    SELECT ?type (COUNT(?s) as ?count)
    WHERE { ?s a ?type }
    GROUP BY ?type
    ORDER BY DESC(?count)'
```

## 데이터 관리

### 전체 데이터 재로드

```bash
# 1. TTL 재생성
python scripts/12_generate_mock_ttl.py

# 2. 데이터셋 초기화
curl -X DELETE 'http://ar_fuseki:3030/$/datasets/ecommerce' -u admin:admin123
curl -X POST 'http://ar_fuseki:3030/$/datasets' \
  -u admin:admin123 -d 'dbType=tdb2&dbName=ecommerce'

# 3. 데이터 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

### 백업

```bash
curl -o backup.nq 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Accept: application/n-quads'
```

## 온톨로지 개발 워크플로우

### 개발 단계 (로컬)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Protégé      │────▶│   TTL 파일      │────▶│    Fuseki       │
│  온톨로지 편집   │     │   저장          │     │   업로드        │
│  & 시각화       │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 1. Protégé로 온톨로지 편집 & 시각화

[Protégé](https://protege.stanford.edu/)는 스탠포드 대학교에서 개발한 온톨로지 편집기입니다.

> 상세 가이드: [docs/protege_guide.md](./protege_guide.md)

**설치:**
```bash
# macOS (Homebrew)
brew install --cask protege

# 또는 공식 사이트에서 다운로드
# https://protege.stanford.edu/products.php
```

**전체 데이터 시각화 (인스턴스 포함):**
```bash
# 통합 TTL 파일 생성
./scripts/export_for_protege.sh

# 결과: exports/ecommerce-full.ttl (약 1.4MB, 39,000 lines)
# Protégé에서 File → Open → exports/ecommerce-full.ttl
```

**온톨로지 스키마만 열기 (가볍게):**
```
File → Open → ontology/ecommerce.ttl
```

**주요 기능:**
- **Entities 탭**: 클래스, 속성, 개인 편집
- **OntoGraf**: 온톨로지 그래프 시각화
- **SPARQL Query**: 쿼리 테스트
- **Reasoner**: OWL 추론 (HermiT, Pellet)

**편집 예시:**
```
1. Classes 탭에서 새 클래스 추가
2. Object Properties 탭에서 관계 정의
3. Data Properties 탭에서 데이터 속성 추가
4. Individuals 탭에서 인스턴스 생성 (테스트용)
```

### 2. TTL 파일로 저장

Protégé에서 편집 후:
1. File → Save (또는 Ctrl+S)
2. 형식: Turtle (`.ttl`)
3. 저장 위치: `ontology/ecommerce.ttl`

**저장 전 확인:**
- Reasoner 실행하여 일관성 검증
- SHACL 제약 조건과 충돌 없는지 확인

### 3. Fuseki에 업로드

```bash
# 온톨로지만 업데이트
curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Content-Type: text/turtle' \
  --data-binary @ontology/ecommerce.ttl

# 또는 전체 재로드 (데이터 포함)
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

### 개발 팁

**버전 관리:**
```bash
# 변경 전 백업
cp ontology/ecommerce.ttl ontology/ecommerce.ttl.bak

# Git으로 변경 추적
git diff ontology/ecommerce.ttl
```

**검증:**
```bash
# TTL 구문 검증 (riot 도구 사용)
riot --validate ontology/ecommerce.ttl

# SHACL 검증
# Fuseki에서 SHACL 검증 활성화 또는 별도 도구 사용
```

**Protégé 플러그인 추천:**
- **OntoGraf**: 그래프 시각화
- **SPARQL Query**: 쿼리 테스트
- **Cellfie**: Excel ↔ OWL 변환

---

## OWL 2 기능 (v2.0에서 추가됨)

### Inverse Properties

```turtle
ecom:purchased owl:inverseOf ecom:purchasedBy .
ecom:placedOrder owl:inverseOf ecom:orderedBy .
```

**용도**: 양방향 관계 탐색
```sparql
# 고객이 구매한 상품 조회
SELECT ?product WHERE { ?customer ecom:purchased ?product }

# 상품을 구매한 고객 조회 (inverse 사용)
SELECT ?customer WHERE { ?product ecom:purchasedBy ?customer }
```

### Functional Properties

```turtle
ecom:customerId a owl:FunctionalProperty .
ecom:orderId a owl:FunctionalProperty .
```

**용도**: 하나의 값만 가질 수 있음 (고유 식별자)

### Disjoint Classes

```turtle
[] a owl:AllDisjointClasses ;
    owl:members ( ecom:Customer ecom:Product ecom:Order ) .
```

**용도**: 클래스 간 중복 방지 (Customer는 Product가 될 수 없음)

### Cardinality Restrictions

```turtle
ecom:Order rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty ecom:containsItem ;
    owl:minCardinality 1
] .
```

**용도**: 최소/최대 관계 수 제약

---

## 참고

- [Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/)
- [SPARQL 1.1 Query](https://www.w3.org/TR/sparql11-query/)
- [SHACL](https://www.w3.org/TR/shacl/)
- [OWL 2](https://www.w3.org/TR/owl2-overview/)
- [Protégé](https://protege.stanford.edu/)
- [Protégé Wiki](https://protegewiki.stanford.edu/)
