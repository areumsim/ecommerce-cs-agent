# LLM Agent 기술 가이드

> **대상 독자**: LLM/Agent 개발 경험이 없는 SW/CV 엔지니어
> **목적**: 이 프로젝트를 이해하고 유지보수/확장할 수 있도록 기초 개념부터 설명

---

## 목차

1. [기초 개념](#1-기초-개념)
2. [이 프로젝트의 구조](#2-이-프로젝트의-구조)
3. [핵심 컴포넌트 상세](#3-핵심-컴포넌트-상세)
4. [데이터 흐름](#4-데이터-흐름)
5. [유사 기술 비교](#5-유사-기술-비교)
6. [실전 개발 가이드](#6-실전-개발-가이드)
7. [트러블슈팅](#7-트러블슈팅)

---

## 1. 기초 개념

### 1.1 LLM (Large Language Model)이란?

**정의**: 대규모 텍스트 데이터로 학습된 언어 모델. 텍스트를 이해하고 생성할 수 있음.

```
┌─────────────────────────────────────────────────────────────────┐
│                         LLM 동작 원리                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   입력 (Prompt)              LLM                출력 (Response)  │
│  ┌─────────────┐         ┌─────────┐         ┌─────────────┐    │
│  │ "환불 정책   │  ──────▶│ GPT-4   │──────▶  │ "환불은 7일  │    │
│  │  알려줘"    │         │ Claude  │         │  이내..."    │    │
│  └─────────────┘         │ Llama   │         └─────────────┘    │
│                          └─────────┘                             │
│                                                                  │
│  * 확률적으로 다음 토큰(단어)을 예측하는 방식으로 텍스트 생성      │
└─────────────────────────────────────────────────────────────────┘
```

**CV와의 비교**:
| 항목 | CV (Computer Vision) | LLM |
|------|---------------------|-----|
| 입력 | 이미지 (픽셀 배열) | 텍스트 (토큰 시퀀스) |
| 출력 | 클래스, 바운딩박스 | 텍스트 시퀀스 |
| 모델 | CNN, ViT | Transformer |
| 학습 | 이미지-레이블 쌍 | 대규모 텍스트 코퍼스 |

### 1.2 Agent란?

**정의**: LLM을 "뇌"로 사용하여 **도구(Tool)**를 호출하고 **작업을 수행**하는 시스템.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent vs 단순 LLM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [단순 LLM]                                                      │
│  사용자: "내 주문 상태 알려줘"                                    │
│  LLM: "주문 상태를 확인하려면 주문번호가 필요합니다" (정보 없음)   │
│                                                                  │
│  [Agent]                                                         │
│  사용자: "내 주문 상태 알려줘"                                    │
│  Agent:                                                          │
│    1. 의도 분류 → "주문 상태 조회"                                │
│    2. 도구 호출 → get_order_status(user_id="user_001")           │
│    3. 결과 조합 → "주문 ORD-001은 배송 중입니다"                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**핵심 구성요소**:
```
Agent = LLM (추론) + Tools (실행) + Memory (기억) + Orchestrator (조율)
```

### 1.3 주요 용어 정리

| 용어 | 설명 | 이 프로젝트에서 |
|------|------|----------------|
| **Prompt** | LLM에 전달하는 입력 텍스트 | `configs/prompts/*.txt` |
| **Token** | LLM이 처리하는 텍스트 단위 (단어/서브워드) | 과금 기준 |
| **Tool/Function** | Agent가 호출할 수 있는 외부 기능 | `src/agents/tools/` |
| **Intent** | 사용자 발화의 의도 | order, policy, claim, recommend |
| **RAG** | 검색 증강 생성 (Retrieval-Augmented Generation) | `src/rag/` |
| **Embedding** | 텍스트를 벡터로 변환 | 유사도 검색에 사용 |
| **Orchestrator** | Agent의 실행 흐름을 제어 | `src/agents/orchestrator.py` |

---

## 2. 이 프로젝트의 구조

### 2.1 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              사용자 요청                                     │
│                          "환불하고 싶어요"                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           1. 입력 가드레일                                   │
│                         (src/guardrails/input_guards.py)                    │
│                                                                              │
│   - 욕설/비속어 필터링                                                       │
│   - 프롬프트 인젝션 방어                                                     │
│   - 입력 길이 제한                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           2. 의도 분류기                                     │
│                    (src/agents/nodes/intent_classifier.py)                  │
│                                                                              │
│   입력: "환불하고 싶어요"                                                    │
│   출력: {intent: "claim", sub_intent: "refund", payload: {...}}            │
│                                                                              │
│   방식:                                                                      │
│   ┌─────────────┐    실패시    ┌─────────────┐                              │
│   │ 키워드 매칭  │ ──────────▶ │ LLM 분류    │                              │
│   │ (정규식)    │             │ (API 호출)  │                              │
│   └─────────────┘             └─────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           3. 오케스트레이터                                  │
│                        (src/agents/orchestrator.py)                         │
│                                                                              │
│   의도에 따라 적절한 핸들러 호출:                                            │
│                                                                              │
│   intent == "order"     → handle_order()     → 주문 서비스                  │
│   intent == "claim"     → handle_claim()     → 티켓 서비스                  │
│   intent == "policy"    → handle_policy()    → RAG 검색                     │
│   intent == "recommend" → handle_recommend() → 추천 서비스                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           4. 도구 실행                                       │
│                          (src/agents/tools/)                                │
│                                                                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │ 주문 조회    │  │ 티켓 생성    │  │ 정책 검색    │  │ 상품 추천    │   │
│   │ order_tools  │  │ ticket_tools │  │ policy_tools │  │ rec_tools    │   │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│          │                 │                 │                 │            │
│          ▼                 ▼                 ▼                 ▼            │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │   SQLite/    │  │   SQLite/    │  │  RAG Index   │  │   Graph DB   │   │
│   │    CSV       │  │    CSV       │  │  (FAISS)     │  │  (Neo4j/     │   │
│   │              │  │              │  │              │  │   NetworkX)  │   │
│   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         5. 출력 가드레일                                     │
│                       (src/guardrails/output_guards.py)                     │
│                                                                              │
│   - PII (개인정보) 마스킹                                                    │
│   - 정책 준수 검증                                                           │
│   - 응답 형식 정규화                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              응답 반환                                       │
│                  "환불 요청이 접수되었습니다. 티켓번호: TKT-001"             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 디렉토리 구조

```
src/
├── agents/                    # Agent 핵심 로직
│   ├── orchestrator.py        # 실행 흐름 제어 (메인 진입점)
│   ├── state.py               # Agent 상태 정의
│   ├── nodes/
│   │   └── intent_classifier.py  # 의도 분류
│   └── tools/                 # 도구 함수들
│
├── llm/                       # LLM 클라이언트
│   └── client.py              # OpenAI/Anthropic/Local API 호출
│
├── rag/                       # 검색 증강 생성
│   └── retriever.py           # 정책 문서 검색
│
├── guardrails/                # 입출력 필터링
│   ├── input_guards.py        # 입력 검증
│   ├── output_guards.py       # 출력 검증
│   └── pipeline.py            # 가드레일 파이프라인
│
├── mock_system/               # 데이터 저장소
│   ├── order_service.py       # 주문 비즈니스 로직
│   ├── ticket_service.py      # 티켓 비즈니스 로직
│   └── storage/               # DB 추상화 (CSV/SQLite)
│
├── graph/                     # 그래프 DB
│   ├── connection.py          # Neo4j 연결
│   ├── repository.py          # 그래프 쿼리
│   └── inmemory.py            # NetworkX 폴백
│
└── recommendation/            # 추천 시스템
    ├── service.py             # 추천 로직
    └── models.py              # 데이터 모델
```

---

## 3. 핵심 컴포넌트 상세

### 3.1 의도 분류 (Intent Classification)

**목적**: 사용자 발화를 분석하여 어떤 작업을 수행할지 결정

**파일**: `src/agents/nodes/intent_classifier.py`

```python
# 의도 분류 흐름
async def classify_intent_async(message: str) -> IntentResult:
    # 1단계: 키워드 기반 빠른 분류 (비용 0)
    result = classify_intent_keyword(message)
    if result.intent != "unknown":
        return result
    
    # 2단계: LLM 기반 정밀 분류 (API 비용 발생)
    return await classify_intent_llm(message)
```

**지원 의도**:
| Intent | Sub-Intent | 예시 발화 |
|--------|------------|----------|
| `order` | list, detail, status, cancel | "주문 목록", "주문 취소해줘" |
| `claim` | create, status | "환불하고 싶어", "교환 요청" |
| `policy` | search | "배송 정책", "반품 규정" |
| `recommend` | similar, personal, trending | "비슷한 상품", "추천해줘" |

**키워드 패턴 추가 방법**:
```python
# src/agents/nodes/intent_classifier.py

INTENT_PATTERNS = {
    "order": {
        "list": [r"주문\s*(목록|내역|리스트)", r"내\s*주문"],
        "cancel": [r"(주문|취소).*(취소|해줘)"],
        # 새 패턴 추가
        "track": [r"배송\s*추적", r"어디까지\s*왔"],  # ← 추가
    },
}
```

### 3.2 오케스트레이터 (Orchestrator)

**목적**: 의도에 따라 적절한 핸들러를 호출하고 결과를 조합

**파일**: `src/agents/orchestrator.py`

```python
# 오케스트레이터 핵심 로직
async def run(state: AgentState) -> AgentState:
    intent = state.intent
    
    # 의도별 핸들러 매핑
    handlers = {
        "order": handle_order,
        "claim": handle_claim,
        "policy": handle_policy,
        "recommend": handle_recommend,
    }
    
    handler = handlers.get(intent, handle_unknown)
    state = await handler(state)
    
    # 가드레일 적용
    state = apply_output_guards(state)
    
    return state
```

**새 의도 추가 방법**:
```python
# 1. 핸들러 함수 정의
async def handle_new_intent(state: AgentState) -> AgentState:
    # 비즈니스 로직
    result = await some_service.process(state.payload)
    state.final_response = {"result": result}
    return state

# 2. handlers 딕셔너리에 등록
handlers = {
    ...
    "new_intent": handle_new_intent,  # ← 추가
}
```

### 3.3 RAG (Retrieval-Augmented Generation)

**목적**: 정책 문서에서 관련 내용을 검색하여 LLM에 컨텍스트로 제공

**파일**: `src/rag/retriever.py`

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAG 동작 흐름                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 오프라인 (인덱싱)                                            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │ 정책     │ ─▶ │ 청킹     │ ─▶ │ 벡터화   │ ─▶ FAISS Index   │
│  │ 문서     │    │ (분할)   │    │(Embedding)│                   │
│  └──────────┘    └──────────┘    └──────────┘                   │
│                                                                  │
│  2. 온라인 (검색)                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ 쿼리     │ ─▶ │ 벡터화   │ ─▶ │ 유사도   │ ─▶ │ Top-K    │  │
│  │"환불정책"│    │          │    │ 검색     │    │ 문서     │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                  │
│  3. 생성                                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Prompt = "다음 정책을 참고하여 답변하세요:\n" +           │   │
│  │          [검색된 문서] +                                  │   │
│  │          "\n\n질문: 환불 정책 알려줘"                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│                      ┌──────┐                                   │
│                      │ LLM  │ ─▶ "환불은 7일 이내..."          │
│                      └──────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

**검색 모드**:
| 모드 | 설명 | 장점 | 단점 |
|------|------|------|------|
| `keyword` | BM25 텍스트 매칭 | 빠름, 의존성 없음 | 의미 이해 못함 |
| `embedding` | 벡터 유사도 | 의미 기반 검색 | FAISS 필요 |
| `hybrid` | 키워드 + 벡터 | 높은 정확도 | 복잡도 증가 |

### 3.4 LLM 클라이언트

**목적**: 다양한 LLM 제공자 (OpenAI, Anthropic, Local)를 통일된 인터페이스로 호출

**파일**: `src/llm/client.py`

```python
# LLM 호출 예시
from src.llm.client import get_llm_client

client = get_llm_client()
response = await client.chat(
    messages=[
        {"role": "system", "content": "당신은 CS 상담원입니다."},
        {"role": "user", "content": "환불하고 싶어요"},
    ],
    temperature=0.7,
    max_tokens=500,
)
```

**설정** (`configs/llm.yaml`):
```yaml
provider: openai  # openai | anthropic | local
model: gpt-4o-mini
temperature: 0.7
max_tokens: 1000

# 로컬 LLM 설정 (vLLM 등)
local:
  base_url: http://localhost:8080/v1
  model: ecommerce-agent-merged
```

### 3.5 가드레일 (Guardrails)

**목적**: 입력/출력을 필터링하여 안전하고 정책에 맞는 응답 보장

**파일**: `src/guardrails/`

```
입력 가드레일 (input_guards.py)
├── 욕설/비속어 필터링
├── 프롬프트 인젝션 방어 ("Ignore previous instructions" 차단)
├── 입력 길이 제한
└── SQL/코드 인젝션 방어

출력 가드레일 (output_guards.py)
├── PII 마스킹 (전화번호: 010-****-1234)
├── 민감 정보 제거
├── 정책 준수 검증
└── 응답 형식 정규화
```

---

## 4. 데이터 흐름

### 4.1 채팅 요청 처리

```
POST /chat
{
  "user_id": "user_001",
  "message": "ORD-123 주문 취소해줘"
}

│
▼ api.py: chat_endpoint()

│
▼ guardrails/pipeline.py: process_input()
  - 입력 검증 통과

│
▼ agents/nodes/intent_classifier.py: classify_intent_async()
  - 키워드 매칭: "취소" → intent="order", sub_intent="cancel"
  - payload: {"order_id": "ORD-123"}

│
▼ agents/orchestrator.py: run()
  - handle_order(state) 호출

│
▼ agents/tools/order_tools.py: cancel_order()
  - mock_system/order_service.py 호출
  - DB에서 주문 상태 변경

│
▼ guardrails/pipeline.py: apply_guards()
  - PII 마스킹 적용

│
▼ 응답 반환
{
  "cancel_result": {"ok": true, "order_id": "ORD-123"}
}
```

### 4.2 추천 요청 처리

```
GET /recommendations/similar/B072K28PPR?top_k=5

│
▼ api.py: get_similar_products()

│
▼ recommendation/service.py: get_similar_products()

│
▼ graph/repository.py: get_similar_products()
  │
  ├─ Neo4j 연결됨? → Cypher 쿼리 실행
  │
  └─ 미연결? → inmemory.py: get_similar_products()
              (NetworkX 그래프에서 검색)

│
▼ 결과 변환 → RecommendationResponse

│
▼ 응답 반환
{
  "products": [...],
  "total_count": 5,
  "is_fallback": false
}
```

---

## 5. 유사 기술 비교

### 5.1 Agent 프레임워크

| 프레임워크 | 특징 | 장점 | 단점 |
|-----------|------|------|------|
| **LangChain** | 가장 인기 있는 프레임워크 | 풍부한 통합, 커뮤니티 | 추상화 과다, 디버깅 어려움 |
| **LlamaIndex** | 데이터 연결 특화 | RAG 최적화 | Agent 기능 제한적 |
| **Semantic Kernel** | MS 개발 | 기업용, 견고함 | 학습 곡선 |
| **AutoGen** | MS Research, 멀티에이전트 | 협업 에이전트 | 복잡한 설정 |
| **이 프로젝트** | 직접 구현 | 완전한 제어, 학습용 | 기능 제한적 |

**이 프로젝트가 직접 구현한 이유**:
1. 프레임워크 의존성 없이 동작 원리 이해
2. 도메인 특화 최적화 가능
3. 경량화 (필요한 기능만 구현)

### 5.2 LLM 제공자

| 제공자 | 모델 | 특징 | 비용 |
|--------|------|------|------|
| **OpenAI** | GPT-4, GPT-4o-mini | 최고 성능, 안정성 | 높음 |
| **Anthropic** | Claude 3 | 긴 컨텍스트, 안전성 | 높음 |
| **Google** | Gemini | 멀티모달 | 중간 |
| **Local (vLLM)** | Llama, Mistral | 비용 0, 프라이버시 | GPU 필요 |

### 5.3 벡터 DB (RAG용)

| DB | 특징 | 사용 사례 |
|----|------|----------|
| **FAISS** | Meta 개발, 로컬, 빠름 | 이 프로젝트 (선택적) |
| **Pinecone** | 관리형, 확장성 | 프로덕션 |
| **Weaviate** | 오픈소스, 하이브리드 검색 | 중규모 |
| **Chroma** | 경량, 임베딩 특화 | 프로토타입 |
| **pgvector** | PostgreSQL 확장 | 기존 PG 사용 시 |

### 5.4 그래프 DB (추천용)

| DB | 특징 | 사용 사례 |
|----|------|----------|
| **Neo4j** | 업계 표준, Cypher 언어 | 이 프로젝트 (선택적) |
| **Amazon Neptune** | AWS 통합 | AWS 환경 |
| **NetworkX** | Python 라이브러리 | 이 프로젝트 (폴백) |
| **TigerGraph** | 대규모 분석 | 엔터프라이즈 |

---

## 6. 실전 개발 가이드

### 6.1 새 의도 추가하기

**예시**: "배송 추적" 기능 추가

```python
# 1. 의도 분류 패턴 추가
# src/agents/nodes/intent_classifier.py

INTENT_PATTERNS = {
    "order": {
        ...
        "track": [r"배송\s*추적", r"어디까지", r"배송\s*현황"],
    },
}

# 2. 핸들러 추가
# src/agents/orchestrator.py

async def handle_order(state: AgentState) -> AgentState:
    sub_intent = state.sub_intent
    
    if sub_intent == "track":
        result = await track_delivery(state.payload.get("order_id"))
        state.final_response = {"tracking": result}
    ...
    return state

# 3. 도구 함수 구현
# src/agents/tools/order_tools.py

async def track_delivery(order_id: str) -> dict:
    # 외부 배송 API 호출 또는 DB 조회
    return {"status": "배송중", "location": "서울 강남구"}
```

### 6.2 LLM 프롬프트 수정

**파일 위치**: `configs/prompts/`

```
configs/prompts/
├── intent_classification.txt   # 의도 분류 프롬프트
├── order_response.txt          # 주문 관련 응답 생성
├── policy_response.txt         # 정책 검색 응답 생성
└── system.txt                  # 시스템 프롬프트 (공통)
```

**프롬프트 작성 팁**:
```
1. 역할 정의: "당신은 이커머스 고객 상담 전문가입니다."
2. 제약 조건: "정책에 없는 내용은 추측하지 마세요."
3. 출력 형식: "JSON 형식으로 응답하세요: {intent, confidence}"
4. 예시 제공: Few-shot 예시로 정확도 향상
```

### 6.3 새 데이터 소스 연결

**예시**: 외부 배송 API 연결

```python
# src/integrations/delivery_api.py

import httpx

class DeliveryAPIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
    
    async def get_tracking(self, tracking_number: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/track/{tracking_number}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            return response.json()
```

### 6.4 테스트 작성

```python
# tests/test_new_feature.py

import pytest
from src.agents.orchestrator import run
from src.agents.state import AgentState

@pytest.mark.asyncio
async def test_track_delivery():
    state = AgentState(
        user_id="user_001",
        intent="order",
        sub_intent="track",
        payload={"order_id": "ORD-123"}
    )
    
    result = await run(state)
    
    assert "tracking" in result.final_response
    assert result.final_response["tracking"]["status"] in ["배송중", "배송완료"]
```

---

## 7. 트러블슈팅

### 7.1 일반적인 문제

| 문제 | 원인 | 해결 |
|------|------|------|
| `no such table` | SQLite 테이블 미생성 | `python scripts/05_migrate_to_sqlite.py` |
| LLM 응답 없음 | API 키 미설정 | `.env`에 `OPENAI_API_KEY` 설정 |
| 의도 분류 실패 | 패턴 미매칭 | `INTENT_PATTERNS`에 패턴 추가 |
| RAG 검색 0건 | 인덱스 미생성 | `python scripts/04_build_index.py` |
| 추천 결과 없음 | 그래프 미로드 | CSV 데이터 확인 |

### 7.2 디버깅 방법

```python
# 1. 의도 분류 확인
from src.agents.nodes.intent_classifier import classify_intent_async

result = await classify_intent_async("환불하고 싶어요")
print(f"Intent: {result.intent}, Sub: {result.sub_intent}")

# 2. 오케스트레이터 상태 확인
from src.agents.orchestrator import run
from src.agents.state import AgentState

state = AgentState(user_id="test", intent="order", sub_intent="list", payload={})
state = await run(state)
print(f"Response: {state.final_response}")

# 3. LLM 직접 호출 테스트
from src.llm.client import get_llm_client

client = get_llm_client()
response = await client.chat([{"role": "user", "content": "테스트"}])
print(response)
```

### 7.3 성능 최적화

```
1. 의도 분류: 키워드 매칭 우선 → LLM 호출 최소화
2. RAG: 벡터 인덱스 사전 로드, 캐싱 활용
3. 추천: 인메모리 그래프로 응답 시간 단축
4. 가드레일: 정규식 컴파일 캐싱
```

---

## 부록: 학습 자료

### 온라인 강의
- [DeepLearning.AI - LangChain 과정](https://www.deeplearning.ai/short-courses/)
- [Hugging Face NLP 코스](https://huggingface.co/learn/nlp-course)

### 논문
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) - Transformer 원논문
- [RAG 원논문](https://arxiv.org/abs/2005.11401)

### 도서
- "Building LLM Apps" - O'Reilly
- "Designing Machine Learning Systems" - Chip Huyen

### 이 프로젝트 문서
- `docs/graph_recommendation_system.md` - 그래프 추천 기술 문서
- `docs/api_reference.md` - API 레퍼런스
- `AGENTS.md` - 프로젝트 가이드
