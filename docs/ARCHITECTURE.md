# 아키텍처 문서

Ecommerce Agent 시스템 아키텍처

## 시스템 개요

한국어 전자상거래 상담 에이전트로, 정책 검색, 주문 관리, 티켓 처리 등의 기능을 제공합니다.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  (Web/Mobile App, API Clients)                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  FastAPI Server (api.py)                                        │
│  - CORS, Authentication, Rate Limiting                          │
│  - Exception Handlers                                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Agent Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Orchestrator │  │   Router     │  │  Guardrails  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │   RAG    │  │  Orders  │  │ Tickets  │  │  Vision  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Data Layer                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   SQLite     │  │   ChromaDB   │  │   LLM API    │          │
│  │   (주문/티켓) │  │   (벡터검색)  │  │   (OpenAI)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## 디렉토리 구조

```
ar_agent/
├── api.py                  # FastAPI 엔트리포인트
├── configs/                # 설정 파일
│   ├── app.yaml           # 앱 전역 설정
│   ├── auth.yaml          # 인증 설정
│   ├── guardrails.yaml    # 가드레일 설정
│   └── llm.yaml           # LLM 설정
├── src/
│   ├── agents/            # 에이전트 모듈
│   │   ├── nodes/         # 의도 분류 노드
│   │   ├── tools/         # 도구 함수
│   │   ├── orchestrator.py # 오케스트레이터
│   │   ├── router.py      # 라우터
│   │   └── state.py       # 상태 관리
│   ├── auth/              # 인증 모듈
│   │   ├── dependencies.py # FastAPI 의존성
│   │   ├── jwt_handler.py # JWT 처리
│   │   ├── password.py    # 비밀번호 해싱
│   │   ├── rate_limiter.py # Rate Limiter
│   │   ├── repository.py  # 사용자 저장소
│   │   └── token_blacklist.py # 토큰 블랙리스트
│   ├── conversation/      # 대화 관리
│   │   ├── manager.py     # 대화 매니저
│   │   ├── models.py      # 데이터 모델
│   │   └── repository.py  # 대화 저장소
│   ├── core/              # 공통 모듈
│   │   ├── exceptions.py  # 커스텀 예외
│   │   └── logging.py     # 로깅 설정
│   ├── guardrails/        # 가드레일
│   │   ├── input_guard.py # 입력 검증
│   │   ├── output_guard.py # 출력 검증
│   │   └── policy_guard.py # 정책 검증
│   ├── llm/               # LLM 클라이언트
│   │   └── client.py      # LLM API 클라이언트
│   ├── monitoring/        # 모니터링
│   │   ├── metrics.py     # Prometheus 메트릭
│   │   └── middleware.py  # 모니터링 미들웨어
│   ├── rag/               # RAG 시스템
│   │   ├── index.py       # 인덱스 관리
│   │   └── retriever.py   # 검색기
│   └── vision/            # 비전 모듈
│       ├── analyzer.py    # 이미지 분석
│       └── defect.py      # 불량 탐지
├── data/                  # 데이터
│   ├── ecommerce.db       # SQLite 데이터베이스
│   ├── policies/          # 정책 문서
│   └── chroma_index/      # ChromaDB 인덱스
├── tests/                 # 테스트
│   ├── test_api.py        # API 테스트
│   ├── test_auth.py       # 인증 테스트
│   └── ...
└── docs/                  # 문서
    ├── api_reference.md   # API 문서
    ├── deployment.md      # 배포 가이드
    └── ARCHITECTURE.md    # 아키텍처 문서 (이 파일)
```

## 컴포넌트 상세

### 1. API Layer (`api.py`)

FastAPI 기반 REST API 서버

**주요 기능:**
- JWT 인증
- CORS 미들웨어
- 전역 예외 핸들러
- Prometheus 메트릭 수집

**엔드포인트 그룹:**
- `/auth/*` - 인증
- `/conversations/*` - 대화 관리
- `/policies/*` - 정책 검색
- `/orders/*` - 주문 관리
- `/tickets/*` - 티켓 관리
- `/vision/*` - 이미지 분석
- `/chat` - 단일 채팅

### 2. Agent Layer

#### Orchestrator (`src/agents/orchestrator.py`)

에이전트 실행 흐름 관리

```python
# 실행 흐름
1. Input Guard (입력 검증)
2. Intent Classification (의도 분류)
3. Router (에이전트 라우팅)
4. Tool Execution (도구 실행)
5. Output Guard (출력 검증)
6. Response Generation
```

#### Router (`src/agents/router.py`)

의도별 에이전트 라우팅

| 의도 | 에이전트 | 설명 |
|------|---------|------|
| policy | PolicyAgent | 정책 검색 |
| order | OrderAgent | 주문 처리 |
| ticket | TicketAgent | 티켓 처리 |
| general | GeneralAgent | 일반 질문 |

#### Guardrails (`src/guardrails/`)

입출력 검증

- **InputGuard**: PII 탐지, 인젝션 방지, 길이 제한
- **OutputGuard**: 톤 검증, 금지어 필터링
- **PolicyGuard**: 정책 준수 검증

### 3. Service Layer

#### RAG System (`src/rag/`)

정책 문서 검색

```
Query → Embedding → Vector Search → Reranking → Response
```

**구성요소:**
- ChromaDB: 벡터 저장소
- BM25: 키워드 검색
- Cross-Encoder: 재정렬

#### Order Service (`src/agents/tools/order_tools.py`)

주문 관리 기능

- 주문 조회
- 주문 상태 확인
- 주문 취소 요청

#### Ticket Service

티켓 관리 기능

- 티켓 생성
- 티켓 조회
- 티켓 해결

#### Vision Service (`src/vision/`)

이미지 분석

- 상품 분석
- 불량 탐지
- CLIP 기반 분류 (선택)

### 4. Data Layer

#### SQLite (`data/ecommerce.db`)

주요 테이블:
- `users` - 사용자 정보
- `orders` - 주문 정보
- `order_items` - 주문 항목
- `tickets` - 티켓 정보
- `conversations` - 대화
- `messages` - 메시지
- `refresh_tokens` - 리프레시 토큰

#### ChromaDB (`data/chroma_index/`)

벡터 인덱스 저장소

- 정책 문서 임베딩
- 의미 기반 검색

### 5. Authentication (`src/auth/`)

JWT 기반 인증

```
Login → Access Token + Refresh Token
         ↓
Request → Bearer Token → Verify → User
         ↓
Expire → Refresh Token → New Access Token
```

**보안 기능:**
- bcrypt 비밀번호 해싱
- JWT 토큰 (30분 만료)
- 리프레시 토큰 (7일 만료)
- 토큰 블랙리스트

## 데이터 흐름

### 대화 처리 흐름

```
1. Client: POST /conversations/{id}/messages
   ↓
2. API: 인증 확인, 대화 소유권 검증
   ↓
3. ConversationManager: 대화 컨텍스트 로드
   ↓
4. Orchestrator:
   a. InputGuard: 입력 검증
   b. IntentClassifier: 의도 분류
   c. Router: 적절한 에이전트 선택
   ↓
5. Agent (예: OrderAgent):
   a. 도구 실행 (DB 조회 등)
   b. LLM 호출 (응답 생성)
   ↓
6. Orchestrator:
   a. OutputGuard: 출력 검증
   b. 메시지 저장
   ↓
7. API: 응답 반환
```

### 정책 검색 흐름

```
1. Client: GET /policies/search?q=환불
   ↓
2. PolicyRetriever:
   a. Query Embedding (text-embedding-3-small)
   b. ChromaDB Vector Search
   c. BM25 Keyword Search
   d. Score Fusion
   e. Cross-Encoder Reranking
   ↓
3. API: 검색 결과 반환
```

## 확장 포인트

### 새 에이전트 추가

1. `src/agents/nodes/` 에 새 에이전트 정의
2. `src/agents/router.py` 에 라우팅 규칙 추가
3. `src/agents/tools/` 에 필요한 도구 추가

### 새 LLM 프로바이더 추가

1. `src/llm/client.py` 에 새 클라이언트 구현
2. `configs/llm.yaml` 에 설정 추가

### 새 데이터 소스 추가

1. `src/mock_system/` 에 저장소 구현
2. 에이전트 도구에서 호출

## 성능 고려사항

- **Rate Limiting**: TokenBucket 알고리즘 (100 토큰, 초당 10 충전)
- **Connection Pooling**: aiohttp ClientSession 재사용
- **Caching**: ChromaDB 인덱스 메모리 캐싱
- **Async**: 모든 I/O 작업 비동기 처리

## 보안 고려사항

- JWT 시크릿 키 환경변수 필수
- 입력 검증 (가드레일)
- SQL Injection 방지 (파라미터화된 쿼리)
- XSS 방지 (출력 이스케이프)
- CORS 제한 (프로덕션)
