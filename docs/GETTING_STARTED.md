# 시작하기 가이드 (Getting Started)

**대상**: 프로젝트에 처음 합류하는 주니어 엔지니어  
**소요 시간**: 약 2-3시간 (환경 설정 + 튜토리얼)

---

## 목차

1. [프로젝트 이해하기](#1-프로젝트-이해하기)
2. [환경 설정](#2-환경-설정)
3. [핵심 코드 탐색](#3-핵심-코드-탐색)
4. [실습 튜토리얼](#4-실습-튜토리얼)
5. [다음 단계](#5-다음-단계)

---

## 1. 프로젝트 이해하기

### 1.1 한 문장 요약

**"고객이 자연어로 질문하면, 지식 그래프에서 정보를 찾아 답변하는 AI 상담 시스템"**

### 1.2 작동 원리 (5분 버전)

```
사용자: "내 주문 보여줘"
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: 의도 파악                                                   │
│  "내 주문 보여줘" → intent: order, sub_intent: list                  │
│  (키워드 매칭 또는 LLM 분류)                                          │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: 도구 실행                                                   │
│  intent=order → order_tools.get_user_orders() 호출                  │
│  RDFRepository → SPARQL 쿼리 → Fuseki → 결과 반환                    │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: 응답 생성                                                   │
│  조회 결과 + 프롬프트 → LLM → 자연어 응답                            │
│  "고객님의 주문 목록입니다: 1. ORD-001 (배송중)..."                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 핵심 기술 스택

| 기술 | 역할 | 알아야 할 정도 |
|------|------|----------------|
| **Python** | 전체 백엔드 | 필수 |
| **FastAPI** | REST API | 기본 |
| **Gradio** | 웹 UI | 기본 |
| **SPARQL** | 데이터 조회 | 기본 쿼리 작성 |
| **RDF/OWL** | 온톨로지 | 개념 이해 |
| **LLM API** | AI 응답 | API 호출 |

---

## 2. 환경 설정

### 2.1 사전 요구사항

```bash
# 필수
- Python 3.10 이상
- Docker & Docker Compose
- Git

# 선택 (권장)
- VS Code + Python 확장
- Protégé (온톨로지 시각화)
```

### 2.2 설치 단계

```bash
# 1. 저장소 클론
git clone <repository-url>
cd ecommerce-cs-agent

# 2. 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 설정
cp .env.example .env  # 또는 직접 생성

# .env 파일에 추가:
OPENAI_API_KEY=your-api-key-here
```

### 2.3 Fuseki (데이터베이스) 실행

```bash
# Docker로 Fuseki 실행
docker run -d --name ar_fuseki \
  -p 31010:3030 \
  -e ADMIN_PASSWORD=admin123 \
  stain/jena-fuseki:4.10.0

# 데이터셋 생성
curl -X POST 'http://localhost:31010/$/datasets' \
  -u admin:admin123 \
  -d 'dbType=tdb2&dbName=ecommerce'

# 데이터 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://localhost:31010/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

### 2.4 실행 확인

```bash
# 데이터 확인 (트리플 수)
curl -s -G 'http://localhost:31010/ecommerce/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }' \
  -H 'Accept: application/json'
# 결과: {"results":{"bindings":[{"count":{"value":"32000"}}]}}

# API 서버 실행
uvicorn api:app --reload --port 8000
# → http://localhost:8000/docs 에서 Swagger UI 확인

# UI 실행 (별도 터미널)
python ui.py
# → http://localhost:7860 에서 UI 확인
```

### 2.5 UI 탭 소개

UI는 4개의 주요 탭으로 구성됩니다:

| 탭 | 용도 | 개발자 유용도 |
|----|------|---------------|
| 💬 고객 상담 | 대화형 CS 테스트 | ⭐⭐ |
| 🔧 관리자 | 데이터 조회/관리 | ⭐⭐ |
| 📊 데이터-지식그래프 | 온톨로지/인스턴스 시각화 | ⭐⭐⭐ |
| 🔧 RDF 데이터 | **SPARQL 쿼리 실행** | ⭐⭐⭐ |

**🔧 RDF 데이터 탭** (개발 시 유용):
- **📝 SPARQL 쿼리**: 쿼리 직접 실행, 예시 버튼 제공
- **➕ 트리플 관리**: 데이터 추가/삭제 테스트
- **🔍 엔티티 브라우저**: 특정 엔티티 상세 조회

### 2.5.1 자연어 → SPARQL 변환

RDF 데이터 탭에서 자연어로 질문하면 SPARQL 쿼리로 자동 변환됩니다.

**사용 방법:**
1. "자연어 질문" 입력란에 질문 입력
2. "🔄 SPARQL로 변환" 클릭
3. 생성된 SPARQL 확인 후 "▶️ 실행"

**예시 질문:**
- "platinum 등급 고객 목록"
- "100달러 이상 상품 목록"
- "user_001 주문 내역"
- "배송중 주문 목록"

**기술 세부사항:**
- 온톨로지(`ontology/ecommerce.ttl`)에서 스키마를 동적 로드
- LLM이 자연어를 SPARQL SELECT 쿼리로 변환
- LIMIT 미지정 시 자동으로 20 추가
- 관련 코드: `ui.py:load_ontology_schema()`, `ui.py:convert_nl_to_sparql()`

### 2.6 설정 파일 확인

```yaml
# configs/rdf.yaml - Fuseki 연결 설정
rdf:
  backend: "fuseki"
fuseki:
  endpoint: "http://localhost:31010/ecommerce"  # 로컬 실행 시
  user: "admin"
  password: "admin123"

# configs/llm.yaml - LLM 설정
default_provider: "openai"
openai:
  model: "gpt-4o-mini"
  temperature: 0.7
```

---

## 3. 핵심 코드 탐색

### 3.1 디렉토리 구조 (중요한 것만)

```
ecommerce-cs-agent/
├── api.py                 # ⭐ FastAPI 서버 (REST API)
├── ui.py                  # ⭐ Gradio UI (웹 인터페이스)
│
├── src/
│   ├── rdf/
│   │   ├── store.py       # ⭐ Fuseki 연결 (SPARQL 실행)
│   │   └── repository.py  # ⭐ 데이터 CRUD (Customer, Product, Order...)
│   │
│   ├── agents/
│   │   ├── orchestrator.py     # ⭐ 메인 흐름 제어
│   │   └── nodes/
│   │       └── intent_classifier.py  # 의도 분류
│   │
│   ├── recommendation/
│   │   └── service.py     # 추천 서비스
│   │
│   ├── llm/
│   │   └── client.py      # LLM API 호출
│   │
│   └── rag/
│       └── retriever.py   # 정책 문서 검색
│
├── ontology/
│   ├── ecommerce.ttl      # ⭐ 온톨로지 스키마 (클래스/관계 정의)
│   └── instances/
│       ├── customers.ttl  # 고객 데이터
│       ├── products.ttl   # 상품 데이터
│       └── orders.ttl     # 주문 데이터
│
└── configs/
    ├── rdf.yaml           # Fuseki 설정
    └── llm.yaml           # LLM 설정
```

### 3.2 핵심 파일 읽기 순서

**1단계: 데이터 레이어 이해** (1시간)
```
1. ontology/ecommerce.ttl      # "어떤 데이터 구조인가?"
2. src/rdf/repository.py       # "데이터를 어떻게 조회하나?"
   - get_customer()            # 고객 조회 예시
   - get_user_orders()         # 주문 조회 예시
```

**2단계: 비즈니스 로직 이해** (1시간)
```
3. src/agents/orchestrator.py  # "요청이 어떻게 처리되나?"
4. src/agents/nodes/intent_classifier.py  # "의도를 어떻게 파악하나?"
```

**3단계: 인터페이스 이해** (30분)
```
5. api.py                      # "API 엔드포인트는?"
6. ui.py                       # "UI는 어떻게 구성?"
```

### 3.3 코드 읽기 팁

```python
# src/rdf/repository.py 예시

def get_customer(self, customer_id: str) -> Optional[Customer]:
    """
    SPARQL 쿼리로 고객 정보 조회
    
    이 메서드가 하는 일:
    1. SPARQL 쿼리 문자열 생성
    2. Fuseki에 쿼리 실행
    3. 결과를 Customer 객체로 변환
    """
    # SPARQL 쿼리 - SQL과 비슷하지만 그래프 데이터용
    query = f"""
        SELECT ?name ?email ?phone
        WHERE {{
            ?customer a ecom:Customer ;          # Customer 타입인 것
                      ecom:customerId "{customer_id}" ;  # ID가 일치
                      ecom:name ?name ;          # 이름 가져오기
                      ecom:email ?email .        # 이메일 가져오기
            OPTIONAL {{ ?customer ecom:phone ?phone }}  # 전화번호 (선택)
        }}
    """
    
    # Fuseki에 쿼리 실행
    results = self.store.query(query)
    
    # 결과를 Python 객체로 변환
    if results:
        r = results[0]
        return Customer(
            customer_id=customer_id,
            name=r["name"],
            email=r["email"],
            phone=r.get("phone"),
        )
    return None
```

---

## 4. 실습 튜토리얼

### 4.1 튜토리얼 1: SPARQL 쿼리 직접 실행

**목표**: Fuseki에 직접 SPARQL 쿼리를 날려보기

> 💡 **Tip**: UI의 **🔧 RDF 데이터 → 📝 SPARQL 쿼리** 탭에서도 동일한 쿼리를 실행할 수 있습니다.

```bash
# 1. 고객 목록 조회
curl -s -G 'http://localhost:31010/ecommerce/sparql' \
  --data-urlencode 'query=
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT ?id ?name ?email
    WHERE {
        ?customer a ecom:Customer ;
                  ecom:customerId ?id ;
                  ecom:name ?name ;
                  ecom:email ?email .
    }
    LIMIT 5
  ' \
  -H 'Accept: application/json' | python -m json.tool

# 2. 특정 고객의 주문 조회
curl -s -G 'http://localhost:31010/ecommerce/sparql' \
  --data-urlencode 'query=
    PREFIX ecom: <http://example.org/ecommerce#>
    SELECT ?orderId ?status ?totalAmount
    WHERE {
        ?customer ecom:customerId "user_001" ;
                  ecom:placedOrder ?order .
        ?order ecom:orderId ?orderId ;
               ecom:status ?status ;
               ecom:totalAmount ?totalAmount .
    }
  ' \
  -H 'Accept: application/json' | python -m json.tool
```

### 4.2 튜토리얼 2: Python에서 Repository 사용

```python
# tutorial_repository.py
from src.rdf.repository import get_rdf_repository

# Repository 인스턴스 가져오기
repo = get_rdf_repository()

# 1. 고객 조회
customer = repo.get_customer("user_001")
print(f"고객: {customer.name} ({customer.email})")

# 2. 고객의 주문 목록
orders = repo.get_user_orders("user_001", limit=3)
for order in orders:
    print(f"  - {order.order_id}: {order.status}, ₩{order.total_amount:,}")

# 3. 협업 필터링 추천
recommendations = repo.get_collaborative_recommendations("user_001", limit=5)
print("\n추천 상품:")
for product, score in recommendations:
    print(f"  - {product.title} (점수: {score})")
```

실행:
```bash
python tutorial_repository.py
```

### 4.3 튜토리얼 3: 새 엔드포인트 추가

**목표**: `/api/customers/{id}/summary` 엔드포인트 추가

```python
# api.py에 추가

from src.rdf.repository import get_rdf_repository

@app.get("/api/customers/{customer_id}/summary")
async def get_customer_summary(customer_id: str):
    """
    고객 요약 정보 조회
    - 기본 정보 + 주문 수 + 총 구매금액
    """
    repo = get_rdf_repository()
    
    # 고객 정보
    customer = repo.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다")
    
    # 주문 목록
    orders = repo.get_user_orders(customer_id, limit=100)
    
    # 요약 계산
    total_orders = len(orders)
    total_amount = sum(o.total_amount for o in orders)
    
    return {
        "customer_id": customer_id,
        "name": customer.name,
        "email": customer.email,
        "membership_level": customer.membership_level,
        "total_orders": total_orders,
        "total_amount": total_amount,
    }
```

테스트:
```bash
curl http://localhost:8000/api/customers/user_001/summary | python -m json.tool
```

### 4.4 튜토리얼 4: 온톨로지에 새 속성 추가

**목표**: Customer에 `vipSince` (VIP 가입일) 속성 추가

```turtle
# ontology/ecommerce.ttl에 추가

ecom:vipSince a owl:DatatypeProperty ;
    rdfs:domain ecom:Customer ;
    rdfs:range xsd:dateTime ;
    rdfs:label "VIP 가입일"@ko ;
    rdfs:comment "고객이 VIP가 된 날짜"@ko .
```

```turtle
# ontology/shacl/ecommerce-shapes.ttl에 추가

ex:CustomerShape sh:property [
    sh:path ecom:vipSince ;
    sh:datatype xsd:dateTime ;
    sh:maxCount 1 ;
] .
```

```python
# src/rdf/repository.py의 Customer 클래스 수정

@dataclass
class Customer:
    customer_id: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    membership_level: str = "bronze"
    vip_since: Optional[datetime] = None  # 추가
    created_at: Optional[datetime] = None
```

```python
# get_customer() 메서드의 SPARQL 쿼리 수정

query = f"""
    SELECT ?name ?email ?phone ?address ?membershipLevel ?createdAt ?vipSince
    WHERE {{
        ?customer a ecom:Customer ;
                  ecom:customerId "{customer_id}" ;
                  ecom:name ?name ;
                  ecom:email ?email .
        OPTIONAL {{ ?customer ecom:phone ?phone }}
        OPTIONAL {{ ?customer ecom:vipSince ?vipSince }}  # 추가
        ...
    }}
"""
```

---

## 5. 다음 단계

### 5.1 학습 경로

| 주차 | 목표 | 학습 내용 |
|------|------|-----------|
| **1주차** | 기본 이해 | SPARQL 기초, Repository 코드 읽기 |
| **2주차** | 기능 추가 | 새 엔드포인트, 새 쿼리 작성 |
| **3주차** | 온톨로지 | OWL 이해, 스키마 수정 |
| **4주차** | 에이전트 | 의도 분류, 오케스트레이터 이해 |

### 5.2 추천 학습 자료

- **SPARQL**: [SPARQL Tutorial](https://jena.apache.org/tutorials/sparql.html)
- **RDF/OWL**: [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/)
- **FastAPI**: [공식 튜토리얼](https://fastapi.tiangolo.com/tutorial/)
- **프로젝트 용어**: [docs/GLOSSARY.md](./GLOSSARY.md)

### 5.3 질문이 있을 때

1. **코드 관련**: `AGENTS.md` 파일 참조 (각 모듈별로 있음)
2. **아키텍처**: `docs/ARCHITECTURE.md` 참조
3. **용어 모르겠을 때**: `docs/GLOSSARY.md` 참조
4. **PRD/로드맵**: `PRD.md` 참조

### 5.4 첫 번째 기여하기

1. **Good First Issue** 라벨 확인
2. 작은 버그 수정 또는 문서 개선부터 시작
3. PR 올리기 전 `pytest -q` 실행 확인

---

## 문제 해결

### Fuseki 연결 안 될 때

```bash
# 컨테이너 상태 확인
docker ps | grep fuseki

# 로그 확인
docker logs ar_fuseki

# 재시작
docker restart ar_fuseki
```

### SPARQL 쿼리 오류

```bash
# 쿼리 문법 검증 (riot 도구)
riot --validate query.sparql

# 또는 Fuseki UI에서 직접 테스트
# http://localhost:31010 → /ecommerce → SPARQL Query
```

### LLM API 오류

```python
# API 키 확인
import os
print(os.getenv("OPENAI_API_KEY"))  # None이면 .env 설정 확인

# configs/llm.yaml 확인
# provider가 맞는지, 모델명이 맞는지
```
