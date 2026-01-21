# E-Commerce Customer Service Agent

한국어 기반 이커머스 고객 상담 에이전트 PoC (Proof of Concept)

**버전**: v1.1.0  
**최종 업데이트**: 2026-01-20  
**데이터 저장소**: Apache Jena Fuseki (RDF Triple Store)  
**트리플 수**: ~32,000

---

## 프로젝트 목표

**RDF 기반 지식 그래프와 LLM을 결합한 지능형 고객 상담 시스템**

이 시스템은 일반적인 LLM 챗봇과 다릅니다:

- **Ontology First**: 모든 사실은 RDF/OWL 기반 온톨로지에서 관리
- **Rule-based Reasoning**: 판단은 명시적 규칙에 의해 결정 (LLM이 판단하지 않음)
- **Explainability by Design**: 왜 이런 결과가 나왔는지 항상 설명 가능
- **LLM as Explainer**: LLM은 의도 분류와 설명 생성에만 사용

### 핵심 기능

- 자연어로 주문 조회, 환불/교환 요청, 정책 질의 처리
- SPARQL 협업 필터링 기반 상품 추천
- 실시간 파이프라인 추적 (디버그 패널)
- 한국어 특화 가드레일 (PII 마스킹, 프롬프트 인젝션 방어)
- **이중 의도 분류 시스템** (LLM + 키워드 폴백)

---

## 데모 UI

### UI Structure (v2.0)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Knowledge Graph Intelligence                                        │
│  [100 Customers] [1,492 Products] [491 Orders] [60 Tickets] [32K+]   │
├─────────────────────────────────────────────────────────────────────┤
│  [Overview] [Intelligence] [Graph Explorer] [Data Tables] [Dev Tools]│
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Tab: Overview                                                        │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  [KPI Cards: Customers | Products | Orders | Tickets | Triples] │   │
│  │  [Quick Actions: CS Agent | Recommendations | Graph | SPARQL]   │   │
│  │  [Technology Stack: RDF | SPARQL | OWL | RAG | LLM | SHACL]     │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Tab: Intelligence > [CS Agent | Recommendation Studio | Policy]      │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  CS Agent: Chat interface with customer context               │   │
│  │  Recommendation Studio: SPARQL-powered recs with WHY panel    │   │
│  │  Policy Search: Hybrid RAG policy lookup                      │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Tab: Graph Explorer                                                  │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  [ER Diagram | Ontology Schema | Instance Graph | Similarity]  │   │
│  │  + Entity Details panel (click node to view)                   │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Tab: Data Tables                                                     │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  [Customers | Orders | Tickets] with filters                   │   │
│  │  Stats overview, status distributions                          │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Tab: Developer Tools                                                 │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  [SPARQL Studio | Triple Manager | Entity Browser | TTL Editor]│   │
│  │  [Evaluation] - Ontology metrics and benchmarks                │   │
│  └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Tab Structure (5 tabs)

| Tab | Description | Key Features |
|-----|-------------|--------------|
| **Overview** | System dashboard | KPI cards, quick actions, technology stack |
| **Intelligence** | AI-powered features | CS Agent chat, Recommendation Studio with WHY panel, Policy search |
| **Graph Explorer** | Ontology visualization | ER Diagram, Schema graph, Instance graph, Similarity graph, Entity details |
| **Data Tables** | Entity management | Customer/Order/Ticket tables with filters, stats distributions |
| **Developer Tools** | Technical tools | SPARQL Studio, Triple Manager, Entity Browser, TTL Editor, Evaluation |

### Feature Details

| Feature | Description | Technology | Data Source |
|---------|-------------|------------|-------------|
| **Natural Language Chat** | Order queries, policy questions | Dual intent classification (LLM + keyword) | RDF + RAG |
| **Order Management** | List/Detail/Status/Cancel/Inquiry | SPARQL CRUD | RDF Repository |
| **Recommendation Studio** | Similar products, trending, categories | SPARQL + vector search | RDF + Embeddings |
| **WHY Panel** | Explainable AI recommendations | Relationship + rule tracing | Knowledge Graph |
| **Policy Search** | Refund/shipping/exchange policies | Hybrid RAG | FAISS + Keyword |
| **NL→SPARQL** | LLM-based SPARQL generation | Dynamic ontology schema | LLM + RDF Schema |
| **Graph Visualization** | Customer-Order-Product relationships | vis.js + Mermaid | RDF Repository |
| **Entity Browser** | Detailed entity inspection | SPARQL queries | RDF Repository |

### Example Queries

```
# Order-related
Show my orders
Order ORD-20251201-001 details
When will my delivery arrive?
Cancel my order

# Policy-related
Refund policy please
How much is shipping?
How do I exchange?

# Recommendations
Recommend products for me
Show similar products
What's trending?

# Claims
I want a refund
This product is defective
```

---

## 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           사용자 인터페이스                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 고객 상담    │  │ 관리자 뷰   │  │ 통합 대시보드│  │ API 클라이언트│     │
│  │ (Gradio)    │  │ (Gradio)    │  │ (Gradio)    │  │ (REST/OpenAI)│     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
└─────────┼────────────────┼────────────────┼────────────────┼───────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI (api.py)                             │   │
│  │  /chat  /orders  /tickets  /recommendations  /policies  /auth   │   │
│  │  /v1/chat/completions (OpenAI 호환)                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Agent Layer                                    │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│  │Intent Classifier│───▶│ Orchestrator  │───▶│   Guardrails  │           │
│  │(키워드+LLM)    │    │ (라우팅/실행) │    │ (입출력 검증) │           │
│  └───────────────┘    └───────┬───────┘    └───────────────┘           │
│                               │                                          │
│         ┌─────────────────────┼─────────────────────┐                   │
│         ▼                     ▼                     ▼                   │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐             │
│  │ Order Tools │      │ Ticket Tools│      │Recommend Tools│             │
│  │ (주문 처리) │      │ (티켓 처리) │      │ (추천 처리)  │             │
│  └─────────────┘      └─────────────┘      └─────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Data Layer                                     │
│                                                                          │
│  ┌──────────────────────────────────────────┐  ┌──────────────────┐    │
│  │         RDF Repository                    │  │  RAG Index       │    │
│  │         (src/rdf/repository.py)           │  │  (JSONL+FAISS)   │    │
│  │                                           │  │                  │    │
│  │  • Customer CRUD                          │  │ • policies.jsonl │    │
│  │  • Product CRUD                           │  │ • embeddings     │    │
│  │  • Order/OrderItem CRUD                   │  │ • vector index   │    │
│  │  • Ticket CRUD                            │  │                  │    │
│  │  • Collaborative recommendations          │  │                  │    │
│  │  • Vector search (embeddings)             │  │                  │    │
│  └────────────────────┬─────────────────────┘  └──────────────────┘    │
│                       │ SPARQL over HTTP                                │
│                       ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   Apache Jena Fuseki                              │  │
│  │  http://ar_fuseki:3030/ecommerce                                  │  │
│  │  ┌────────────────────────────────────────────────────────────┐  │  │
│  │  │  TDB2 Dataset: /ecommerce (~32,000 triples)                 │  │  │
│  │  │  • ontology/ecommerce.ttl (OWL ontology)                    │  │  │
│  │  │  • ontology/shacl/*.ttl (SHACL validation)                  │  │  │
│  │  │  • ontology/instances/*.ttl (customers, products, orders)   │  │  │
│  │  └────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         External Services                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │
│  │   OpenAI    │  │  Anthropic  │  │  Local LLM  │                     │
│  │   API       │  │   API       │  │  (vLLM)     │                     │
│  └─────────────┘  └─────────────┘  └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 의도 분류 시스템 (Dual Classification)

이 시스템은 **LLM-First with Keyword Fallback** 전략을 사용합니다:

```
사용자 입력
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    의도 분류 (classify_intent_async)         │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. LLM 분류 시도 (llm_classification.enabled=true)   │    │
│  │    ├─ 성공 + 신뢰도 >= threshold → IntentResult 반환 │    │
│  │    └─ 실패 또는 저신뢰 → 다음 단계                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2. 키워드 분류 (폴백)                                │    │
│  │    ├─ 주문 ID 패턴 매칭 (ORD-xxx, ORD_xxx)           │    │
│  │    ├─ 의도별 키워드 매칭 (configs/intents.yaml)      │    │
│  │    └─ 항상 결과 반환 (unknown 포함)                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
IntentResult(
    intent="order",           # 주 의도
    sub_intent="status",      # 세부 의도
    payload={"order_id": "ORD-001"},  # 추출된 파라미터
    confidence="high",        # 신뢰도
    source="keyword",         # 분류 출처: "keyword" 또는 "llm"
    reason="주문 ID + 상태 키워드 탐지"  # 분류 근거
)
```

### 지원 의도 (Intent) 목록

| Intent | Sub-Intent | 설명 | 키워드 예시 |
|--------|------------|------|------------|
| `order` | `list` | 주문 목록 조회 | "주문 보여줘", "내 주문" |
| `order` | `detail` | 주문 상세 조회 | "ORD-001 상세", "주문 정보" |
| `order` | `status` | 배송 상태 조회 | "배송 어디야", "상태 알려줘" |
| `order` | `cancel` | 주문 취소 | "취소하고 싶어", "주문 취소" |
| `claim` | - | 환불/교환 요청 | "환불", "교환", "불량" |
| `policy` | - | 정책 질의 | "정책 알려줘", "어떻게 해" |
| `recommend` | `similar` | 유사 상품 추천 | "비슷한 거", "유사한 상품" |
| `recommend` | `personal` | 개인화 추천 | "추천해줘" |
| `recommend` | `trending` | 인기 상품 | "인기 상품", "베스트" |
| `recommend` | `together` | 함께 구매 | "같이 사는 거", "세트" |
| `recommend` | `category` | 카테고리 추천 | "카테고리", "분야" |
| `general` | - | 일반 대화 | "안녕", "고마워" |

### 실행 파이프라인

```
사용자 입력
    │
    ▼
┌─────────────────────────────────────────────┐
│ 1. Guardrails (입력)                         │
│    ├─ 길이 검사                              │
│    ├─ PII 감지 및 마스킹                     │
│    ├─ 프롬프트 인젝션 탐지                   │
│    └─ 금지어 필터링                          │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 2. Intent Classification                     │
│    ├─ LLM 분류 시도                          │
│    └─ 키워드 폴백                            │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 3. Orchestrator                              │
│    ├─ 의도별 라우팅                          │
│    ├─ 도구 실행 (RDF/RAG)                    │
│    └─ 추적 기록 (add_trace)                  │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 4. 응답 생성                                 │
│    ├─ LLM 응답 (사용 가능 시)                │
│    └─ 템플릿 응답 (폴백)                     │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 5. Guardrails (출력)                         │
│    ├─ PII 마스킹                             │
│    ├─ 정책 위반 검사                         │
│    └─ 가격/재고 검증                         │
└─────────────────────────────────────────────┘
    │
    ▼
최종 응답
```

---

## 데이터

### 엔티티 통계

| 엔티티 | 개수 | 소스 | 설명 |
|--------|------|------|------|
| Products | 1,492 | Amazon Reviews | 상품 정보, 평점, 리뷰 수 |
| Orders | 491 | Mock 생성 | 주문 정보, 상태, 금액 |
| OrderItems | 1,240 | Mock 생성 | 주문 항목, 수량, 단가 |
| Customers | 100 | Mock 생성 | 고객 정보, 등급 |
| Tickets | 60 | Mock 생성 | 지원 티켓 |
| Similarities | 4,416 | 자동 생성 | 상품 간 유사도 관계 |
| Embeddings | 1,492 | 자동 생성 | 384-dim 벡터 (전체 상품) |
| Policy Docs | 63 | 수동 작성 | 정책 문서 |
| SHACL Shapes | 208 | 수동 작성 | 데이터 검증 규칙 |
| **Total Triples** | ~32,000 | Fuseki | - |

### 온톨로지 구조

```
ontology/
├── ecommerce.ttl              # OWL 온톨로지 스키마 (174 triples)
├── shacl/
│   └── ecommerce-shapes.ttl   # SHACL 검증 규칙 (208 shapes)
└── instances/
    ├── customers.ttl          # 고객 인스턴스 (100)
    ├── products.ttl           # 상품 인스턴스 (1,492)
    ├── orders.ttl             # 주문/주문항목 인스턴스 (1,731)
    ├── tickets.ttl            # 티켓 인스턴스 (60)
    ├── similarities.ttl       # 상품 유사도 관계 (4,416)
    └── embeddings.ttl         # 벡터 임베딩 (1,492)
```

### ER 다이어그램

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Customer   │       │    Order    │       │   Product   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ customerId  │──┐    │ orderId     │    ┌──│ productId   │
│ name        │  │    │ status      │    │  │ title       │
│ email       │  │    │ orderDate   │    │  │ brand       │
│ phone       │  └───▶│ totalAmount │    │  │ price       │
│ address     │       │ orderedBy   │────┘  │ avgRating   │
│ membership  │       └──────┬──────┘       └──────┬──────┘
└──────┬──────┘              │                     │
       │                     │                     │
       │              ┌──────▼──────┐              │
       │              │  OrderItem  │              │
       │              ├─────────────┤              │
       │              │ quantity    │◀─────────────┘
       │              │ unitPrice   │  hasProduct
       │              │ hasProduct  │
       │              │ belongsTo   │
       │              └─────────────┘
       │
       │              ┌─────────────┐
       └─────────────▶│   Ticket    │
         hasTicket    ├─────────────┤
                      │ ticketId    │
                      │ issueType   │
                      │ status      │
                      │ priority    │
                      └─────────────┘
```

---

## 빠른 시작

### 1. 환경 설정

```bash
git clone <repository>
cd ecommerce-cs-agent

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="your-api-key"
```

### 2. Fuseki 실행 (Docker)

```bash
# Fuseki 컨테이너 실행
docker run -d --name ar_fuseki \
  -p 31010:3030 \
  -e ADMIN_PASSWORD=admin123 \
  stain/jena-fuseki:4.10.0

# 데이터셋 생성
curl -X POST 'http://localhost:31010/$/datasets' \
  -u admin:admin123 \
  -d 'dbType=tdb2&dbName=ecommerce'
```

### 3. 데이터 로드

```bash
# 온톨로지 및 인스턴스 데이터 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://localhost:31010/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done

# 로드 확인
curl 'http://localhost:31010/ecommerce/sparql' \
  -u admin:admin123 \
  -H 'Accept: application/json' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'
```

### 4. 실행

```bash
# 서비스 관리 스크립트 (권장)
./services.sh start          # UI + API 모두 시작
./services.sh start ui       # UI만 시작 (port 7860)
./services.sh start api      # API만 시작 (port 8000)
./services.sh stop           # 모두 중지
./services.sh restart        # 모두 재시작
./services.sh status         # 상태 확인
./services.sh logs ui        # UI 로그 확인
./services.sh logs api       # API 로그 확인

# 직접 실행 (개발용)
python ui.py                 # → http://localhost:7860
uvicorn api:app --reload     # → http://localhost:8000/docs
```

**서비스 관리 특징:**
- 시작 시 기존 프로세스 자동 정리 (좀비 프로세스 방지)
- PID 파일 기반 프로세스 추적 (`.ui.pid`, `.api.pid`)
- 로그 파일 자동 생성 (`.ui.log`, `.api.log`)
- SIGTERM → SIGKILL 순차적 종료로 깔끔한 정리

---

## 설정

### LLM (`configs/llm.yaml`)

```yaml
default_provider: "openai"

openai:
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 1024

anthropic:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-3-haiku-20240307

local:
  base_url: "http://localhost:8080/v1"
  model: "local-model"
```

### RDF (`configs/rdf.yaml`)

```yaml
rdf:
  backend: "fuseki"  # fuseki | rdflib

fuseki:
  endpoint: "http://ar_fuseki:3030/ecommerce"
  user: "admin"
  password: "admin123"
```

### 의도 분류 (`configs/intents.yaml`)

```yaml
# LLM 기반 의도 분류 설정
llm_classification:
  enabled: true                    # LLM 의도 분류 활성화
  fallback_to_keyword: true        # LLM 실패 시 키워드 폴백
  confidence_threshold: "medium"   # 최소 신뢰도 (low/medium/high)
  timeout: 10                      # LLM 호출 타임아웃 (초)

# 주문 ID 패턴
patterns:
  order_id: "\\bORD[-_][A-Za-z0-9_-]+\\b"

# 의도별 키워드
intents:
  order:
    keywords: ["주문", "배송", "취소", "결제", "구매"]
    sub_intents:
      cancel:
        keywords: ["취소"]
      status:
        keywords: ["상태", "배송", "어디"]
      detail:
        keywords: ["상세", "내역", "정보"]

  claim:
    keywords: ["환불", "교환", "불량", "클레임", "고장"]

  recommend:
    keywords: ["추천", "비슷한", "유사한", "인기", "트렌드"]
```

### RAG (`configs/rag.yaml`)

```yaml
retrieval:
  mode: "hybrid"           # keyword | embedding | hybrid
  hybrid_alpha: 0.7        # 벡터 검색 가중치 (0=키워드만, 1=벡터만)
  min_score: 0.0           # 최소 점수 필터
  use_reranking: false     # 리랭킹 사용 여부

embedding:
  model: "intfloat/multilingual-e5-small"
  dimension: 384
```

### 가드레일 (`configs/guardrails.yaml`)

```yaml
input:
  max_length: 2000

pii_patterns:
  phone_kr:
    pattern: "01[016789]-?\\d{3,4}-?\\d{4}"
    mask: "***-****-****"
  email:
    pattern: "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"
    mask: "***@***.***"
  rrn:
    pattern: "\\d{6}-[1-4]\\d{6}"
    mask: "******-*******"

injection_patterns:
  - "ignore previous"
  - "system prompt"
  - "이전 지시 무시"

blocked_words:
  - "비밀번호"
  - "password"
```

---

## 프로젝트 구조

```
ecommerce-cs-agent/
├── api.py                 # FastAPI 서버 (990 lines)
├── ui.py                  # Gradio Web UI (2,400+ lines)
│
├── src/
│   ├── agents/            # 에이전트 레이어
│   │   ├── orchestrator.py        # 오케스트레이터 (의도→도구→응답)
│   │   ├── state.py               # AgentState 데이터클래스
│   │   ├── nodes/
│   │   │   ├── intent_classifier.py   # 이중 의도 분류기
│   │   │   ├── order_agent.py         # 주문 처리
│   │   │   ├── claim_agent.py         # 클레임 처리
│   │   │   └── recommend_agent.py     # 추천 처리
│   │   └── tools/
│   │       └── order_tools.py         # 주문 도구 함수
│   │
│   ├── rdf/               # RDF 데이터 레이어
│   │   ├── store.py               # FusekiStore, UnifiedRDFStore
│   │   └── repository.py          # RDFRepository (모든 CRUD)
│   │
│   ├── rag/               # RAG 정책 검색
│   │   ├── retriever.py           # PolicyRetriever (하이브리드 검색)
│   │   ├── embedder.py            # Embedder (sentence-transformers)
│   │   └── indexer.py             # 인덱스 빌더
│   │
│   ├── llm/               # LLM 클라이언트
│   │   ├── client.py              # 멀티 프로바이더 클라이언트
│   │   └── router.py              # 의도별 LLM 라우팅
│   │
│   ├── guardrails/        # 가드레일
│   │   ├── input_guards.py        # 입력 검증 (PII, 인젝션)
│   │   ├── output_guards.py       # 출력 검증 (정책 위반)
│   │   └── pipeline.py            # 통합 파이프라인
│   │
│   ├── auth/              # 인증
│   │   ├── jwt_handler.py         # JWT 토큰 처리
│   │   └── password.py            # 비밀번호 해싱
│   │
│   ├── conversation/      # 대화 관리
│   │   ├── manager.py             # 세션 관리
│   │   └── repository.py          # SQLite 저장소
│   │
│   ├── recommendation/    # 추천 서비스
│   │   └── service.py             # RecommendationService
│   │
│   ├── vision/            # 이미지 분석 (선택)
│   │   └── pipeline.py            # 이미지 분석 파이프라인
│   │
│   ├── core/              # 공통
│   │   ├── exceptions.py          # 커스텀 예외
│   │   └── tracer.py              # 실행 추적
│   │
│   └── config.py          # 설정 로더
│
├── ontology/              # RDF 온톨로지
│   ├── ecommerce.ttl              # OWL 스키마
│   ├── shacl/                     # SHACL 검증 규칙
│   └── instances/                 # 인스턴스 데이터
│
├── configs/               # YAML 설정
│   ├── llm.yaml
│   ├── rdf.yaml
│   ├── rag.yaml
│   ├── intents.yaml
│   ├── guardrails.yaml
│   └── auth.yaml
│
├── scripts/               # 데이터 파이프라인
│   ├── 03_generate_mock_csv.py    # Mock 데이터 생성
│   ├── 12_generate_mock_ttl.py    # CSV → TTL 변환
│   └── 15_generate_embeddings.py  # 임베딩 생성
│
├── data/                  # 생성된 데이터 (gitignore)
│   ├── mock_csv/                  # Mock CSV 데이터
│   └── processed/                 # RAG 인덱스
│
├── docs/                  # 문서
│   ├── ARCHITECTURE.md            # 아키텍처 상세
│   ├── TECHNOLOGY_OVERVIEW.md     # 기술 철학
│   ├── STATUS.md                  # 구현 현황
│   ├── FIRST_DAY_GUIDE.md         # 온보딩 가이드
│   └── GLOSSARY.md                # 용어 사전
│
└── tests/                 # pytest
    ├── test_rdf.py
    ├── test_auth.py
    └── test_agents.py
```

---

## 테스트

```bash
# 전체 테스트
pytest -q

# 모듈별 테스트
pytest tests/test_rdf.py -q        # RDF 모듈
pytest tests/test_auth.py -q       # 인증 모듈
pytest tests/test_agents.py -q     # 에이전트 모듈

# 커버리지
pytest --cov=src --cov-report=html
```

---

## API 엔드포인트

### REST API

```
# 인증
POST /auth/register          # 회원가입
POST /auth/login             # 로그인
POST /auth/refresh           # 토큰 갱신
GET  /auth/me                # 현재 사용자
POST /auth/logout            # 로그아웃

# 주문 (RDF Repository)
GET  /users/{user_id}/orders         # 사용자 주문 목록
GET  /orders/{order_id}              # 주문 상세
GET  /orders/{order_id}/status       # 주문 상태
POST /orders/{order_id}/cancel       # 주문 취소

# 티켓 (RDF Repository)
POST /tickets                        # 티켓 생성
GET  /tickets/{ticket_id}            # 티켓 조회
POST /tickets/{ticket_id}/resolve    # 티켓 해결

# 추천 (RDF Repository + Vector)
GET  /recommendations/similar/{product_id}      # 유사 상품
GET  /recommendations/personalized/{user_id}    # 개인화 추천
GET  /recommendations/trending                  # 인기 상품
GET  /recommendations/bought-together/{product_id}  # 함께 구매

# 정책 (RAG Index)
GET  /policies/search?q=...          # 정책 검색

# 채팅
POST /chat                           # 대화

# 헬스체크
GET  /health                         # 상태 확인
GET  /ready                          # 준비 상태
GET  /metrics                        # Prometheus 메트릭
```

### OpenAI 호환 API

```
GET  /v1/models              # 모델 목록
POST /v1/chat/completions    # 채팅 완료

# LibreChat, OpenWebUI 등과 호환
```

---

## 기술 스택

### 사용 중

| 카테고리 | 기술 | 버전 | 용도 |
|---------|------|------|------|
| **Runtime** | Python | 3.10+ | 런타임 |
| **API** | FastAPI | 0.128+ | REST API 서버 |
| **UI** | Gradio | 6.3+ | Web UI |
| **RDF** | Apache Jena Fuseki | 4.10.0 | Triple Store |
| **RDF Client** | RDFLib | 7.5+ | SPARQL 클라이언트 |
| **Vector Search** | FAISS | 1.13+ | 벡터 유사도 검색 |
| **Embeddings** | sentence-transformers | 5.2+ | 임베딩 생성 |
| **LLM** | OpenAI SDK | 2.14+ | LLM API |
| **LLM** | Anthropic SDK | 0.71+ | LLM API (대안) |
| **Auth** | python-jose | 3.3+ | JWT 처리 |
| **Auth** | passlib | 1.7+ | 비밀번호 해싱 |
| **Validation** | Pydantic | 2.12+ | 데이터 검증 |
| **Config** | PyYAML | 6.0+ | 설정 파일 |
| **Testing** | pytest | 9.0+ | 테스트 |
| **Monitoring** | prometheus-client | 0.23+ | 메트릭 수집 |

### 확장 시 고려

| 기술 | 용도 | 도입 시기 |
|------|------|----------|
| **Neo4j** | 대규모 그래프 DB | GDS 알고리즘 필요 시 |
| **vLLM/Ollama** | 로컬 LLM 서빙 | 비용 절감, 프라이버시 필요 시 |
| **Redis** | 캐싱, 세션 관리 | 다중 인스턴스 배포 시 |
| **Kafka** | 이벤트 스트리밍 | 실시간 처리 필요 시 |

---

## 문서 가이드

이 프로젝트의 문서들은 **각각 역할이 명확히 분리**되어 있습니다.

| 문서 | 역할 | 내용 | 분량 |
|------|------|------|------|
| [TECHNOLOGY_OVERVIEW.md](docs/TECHNOLOGY_OVERVIEW.md) | 개념 지도 | 시스템 철학, 아키텍처 원칙, LLM 경계 | ~280줄 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 설계도 | 실행 흐름, 컴포넌트 상세, 데이터 구조 | ~1,400줄 |
| [STATUS.md](docs/STATUS.md) | 구현 현황 | 버전, 구현된 기능, 알려진 이슈 | ~160줄 |
| [FIRST_DAY_GUIDE.md](docs/FIRST_DAY_GUIDE.md) | 온보딩 | 첫날 실습 가이드, 체크리스트 | ~220줄 |
| [GLOSSARY.md](docs/GLOSSARY.md) | 용어 사전 | 기술 용어 정의, 데이터 구조 | ~210줄 |

### 읽는 순서 (권장)

1. **Day 1 오전**: TECHNOLOGY_OVERVIEW.md (개념 이해)
2. **Day 1 오후**: FIRST_DAY_GUIDE.md + UI 실습
3. **Day 2**: ARCHITECTURE.md (아키텍처 상세)
4. **필요 시**: GLOSSARY.md (용어 참조), STATUS.md (현황 확인)

### 핵심 원칙

1. **Ontology First**: 모든 사실은 RDF/OWL 기반 온톨로지에서 관리
2. **Rule-based Reasoning**: 판단은 명시적 규칙에 의해 결정
3. **LLM as Explainer**: LLM은 의도 분류와 설명 생성에만 사용 (판단 금지)
4. **Truth Order**: Ontology → Rules → GNN → Explanation → UI

---

## 라이선스

MIT License
