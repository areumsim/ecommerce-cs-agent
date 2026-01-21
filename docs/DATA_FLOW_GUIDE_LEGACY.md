# 데이터 흐름 가이드 (Legacy)

> **Note**: 이 문서는 RDF/Fuseki 마이그레이션 이전 아키텍처 기준입니다.  
> 현재 아키텍처는 `ARCHITECTURE.md` 참조.

한국어 전자상거래 고객 상담 에이전트의 API 요청/응답 포맷과 내부 데이터 흐름을 상세히 설명합니다.

---

## 목차

- [1장: 개요](#1장-개요)
- [2장: API 레퍼런스](#2장-api-레퍼런스)
- [3장: 내부 데이터 흐름](#3장-내부-데이터-흐름)
  - [3.3 입력 가드레일 상세 흐름](#33-입력-가드레일-상세-흐름)
  - [3.4 출력 가드레일 상세 흐름](#34-출력-가드레일-상세-흐름)
  - [3.5 LLM 라우팅 폴백 메커니즘](#35-llm-라우팅-폴백-메커니즘)
  - [3.6 RAG 검색 및 리랭킹 폴백](#36-rag-검색-및-리랭킹-폴백)
  - [3.7 대화 히스토리 자동 구성](#37-대화-히스토리-자동-구성)
  - [3.8 에이전트 라우터 폴백 체인](#38-에이전트-라우터-폴백-체인)
- [4장: End-to-End 시나리오](#4장-end-to-end-시나리오)
- [5장: 에러 응답 및 예외 처리](#5장-에러-응답-및-예외-처리)

---

# 1장: 개요

## 1.1 문서 목적

이 문서는 다음을 목표로 합니다:

1. **API 사용법 이해**: 각 엔드포인트의 요청/응답 JSON 포맷을 실제 샘플과 함께 제공
2. **내부 흐름 이해**: 사용자 메시지가 시스템 내부에서 어떻게 처리되는지 단계별 추적
3. **디버깅 지원**: 문제 발생 시 어느 단계에서 데이터가 어떻게 변환되는지 파악

## 1.2 관련 문서

- `docs/TECHNOLOGY_GUIDE.md` - 기술 개념 및 아키텍처 설명
- `README.md` - 프로젝트 개요 및 빠른 시작 가이드

## 1.3 전체 데이터 흐름 개요

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           전체 시스템 데이터 흐름                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐      HTTP Request       ┌──────────────────────────────────┐
│              │  ───────────────────▶   │                                  │
│   클라이언트   │                         │         FastAPI Server          │
│  (Frontend)  │  ◀───────────────────   │           (api.py)              │
│              │      HTTP Response      │                                  │
└──────────────┘                         └─────────────┬────────────────────┘
                                                       │
                                                       ▼
                              ┌─────────────────────────────────────────────┐
                              │            인증 & 검증 레이어                 │
                              │  ┌─────────────┐  ┌─────────────────────┐   │
                              │  │ JWT 검증    │  │ Pydantic 검증       │   │
                              │  │ Rate Limit  │  │ Input Guardrail    │   │
                              │  └─────────────┘  └─────────────────────┘   │
                              └─────────────────────────────────────────────┘
                                                       │
                                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            에이전트 시스템                                    │
│                                                                             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────────────┐ │
│  │  Intent          │    │   Agent          │    │     Specialist        │ │
│  │  Classifier      │───▶│   Router         │───▶│     Agents           │ │
│  │                  │    │                  │    │                       │ │
│  │  "환불 정책?"    │    │  intent=policy   │    │  ┌─────────────────┐  │ │
│  │       ↓          │    │       ↓          │    │  │ PolicySpecialist│  │ │
│  │  IntentResult    │    │  AgentContext    │    │  │ OrderSpecialist │  │ │
│  └──────────────────┘    └──────────────────┘    │  │ ClaimSpecialist │  │ │
│                                                   │  └─────────────────┘  │ │
│                                                   └───────────────────────┘ │
│                                                              │              │
│                                                              ▼              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Orchestrator                                  │  │
│  │  ┌─────────────┐   ┌─────────────┐   ┌──────────────────────────┐   │  │
│  │  │ RAG 검색    │   │ LLM 호출    │   │ Output Guardrail        │   │  │
│  │  │ (Policy)    │   │ (응답 생성)  │   │ (PII 마스킹, 필터링)     │   │  │
│  │  └─────────────┘   └─────────────┘   └──────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                              │              │
└──────────────────────────────────────────────────────────────┼──────────────┘
                                                               │
                                                               ▼
                              ┌─────────────────────────────────────────────┐
                              │              최종 응답 생성                   │
                              │  {                                          │
                              │    "response": "환불 정책에 대해...",         │
                              │    "intent": "policy",                      │
                              │    "data": { "hits": [...] }                │
                              │  }                                          │
                              └─────────────────────────────────────────────┘
```

## 1.4 핵심 데이터 구조 요약

| 단계 | 데이터 구조 | 설명 |
|------|------------|------|
| 1. API 요청 | `MessageCreate` | 클라이언트가 보내는 메시지 |
| 2. 의도 분류 | `IntentResult` | 분류된 의도와 파라미터 |
| 3. 라우팅 | `AgentContext` | 에이전트에 전달되는 컨텍스트 |
| 4. 처리 | `AgentResponse` | 전문가 에이전트의 응답 |
| 5. 최종 응답 | `final_response` | 클라이언트에 반환되는 JSON |

## 1.5 의도(Intent) 유형

| Intent | 설명 | Sub-Intent |
|--------|------|------------|
| `order` | 주문 관련 | `list`, `status`, `detail`, `cancel` |
| `claim` | 클레임/티켓 | - |
| `policy` | 정책 문의 | - |
| `general` | 일반 대화 | - |
| `unknown` | 분류 불가 | - |

---

# 2장: API 레퍼런스

이 장에서는 모든 API 엔드포인트의 요청/응답 포맷을 JSON 샘플과 함께 설명합니다.

## 2.1 인증 API

### 2.1.1 회원가입

```
POST /auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "name": "홍길동"
}
```

**Response (201 Created):**
```json
{
  "id": "user_a1b2c3d4e5f6",
  "email": "user@example.com",
  "name": "홍길동",
  "role": "user",
  "is_active": true,
  "created_at": "2025-12-26T10:30:00"
}
```

**Error Response (400 Bad Request):**
```json
{
  "detail": "이메일이 이미 존재합니다"
}
```

**curl 예시:**
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123",
    "name": "홍길동"
  }'
```

---

### 2.1.2 로그인

```
POST /auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyX2ExYjJjM2Q0ZTVmNiIsImVtYWlsIjoidXNlckBleGFtcGxlLmNvbSIsInJvbGUiOiJ1c2VyIiwidHlwZSI6ImFjY2VzcyIsImV4cCI6MTczNTIwMTYwMCwiaWF0IjoxNzM1MTk4MDAwfQ.xxxxx",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyX2ExYjJjM2Q0ZTVmNiIsInR5cGUiOiJyZWZyZXNoIiwiZXhwIjoxNzM1ODAyODAwLCJpYXQiOjE3MzUxOTgwMDB9.yyyyy",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Response (401 Unauthorized):**
```json
{
  "detail": "이메일 또는 비밀번호가 올바르지 않습니다"
}
```

**curl 예시:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123"
  }'
```

---

### 2.1.3 토큰 갱신

```
POST /auth/refresh
```

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.새로운토큰...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.새로운리프레시...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Response (401 Unauthorized):**
```json
{
  "detail": "유효하지 않은 리프레시 토큰입니다"
}
```

---

### 2.1.4 현재 사용자 정보

```
GET /auth/me
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "id": "user_a1b2c3d4e5f6",
  "email": "user@example.com",
  "name": "홍길동",
  "role": "user",
  "is_active": true,
  "created_at": "2025-12-26T10:30:00"
}
```

**curl 예시:**
```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

### 2.1.5 로그아웃

```
POST /auth/logout
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "message": "로그아웃 완료 (3개 토큰 무효화)"
}
```

---

## 2.2 대화 API

### 2.2.1 대화 생성

```
POST /conversations
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "title": "배송 문의",
  "metadata": {
    "category": "shipping",
    "priority": "high"
  }
}
```

**Response (201 Created):**
```json
{
  "id": "conv_1735198200123",
  "user_id": "user_a1b2c3d4e5f6",
  "title": "배송 문의",
  "status": "active",
  "message_count": 0,
  "created_at": "2025-12-26T10:30:00",
  "updated_at": "2025-12-26T10:30:00"
}
```

---

### 2.2.2 대화 목록 조회

```
GET /conversations?status=active&limit=20
Authorization: Bearer {access_token}
```

**Query Parameters:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|-------|------|
| `status` | string | - | `active`, `closed`, `expired` |
| `limit` | int | 20 | 1-100 |

**Response (200 OK):**
```json
[
  {
    "id": "conv_1735198200123",
    "user_id": "user_a1b2c3d4e5f6",
    "title": "배송 문의",
    "status": "active",
    "message_count": 3,
    "created_at": "2025-12-26T10:30:00",
    "updated_at": "2025-12-26T10:35:00"
  },
  {
    "id": "conv_1735197800456",
    "user_id": "user_a1b2c3d4e5f6",
    "title": "환불 정책",
    "status": "closed",
    "message_count": 5,
    "created_at": "2025-12-26T09:00:00",
    "updated_at": "2025-12-26T09:15:00"
  }
]
```

---

### 2.2.3 대화 상세 조회

```
GET /conversations/{conversation_id}
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "conversation": {
    "id": "conv_1735198200123",
    "user_id": "user_a1b2c3d4e5f6",
    "title": "배송 문의",
    "status": "active",
    "message_count": 2,
    "created_at": "2025-12-26T10:30:00",
    "updated_at": "2025-12-26T10:35:00"
  },
  "messages": [
    {
      "id": "msg_001",
      "conversation_id": "conv_1735198200123",
      "role": "user",
      "content": "배송은 언제 도착하나요?",
      "intent": "order_status",
      "metadata": null,
      "created_at": "2025-12-26T10:30:00"
    },
    {
      "id": "msg_002",
      "conversation_id": "conv_1735198200123",
      "role": "assistant",
      "content": "배송은 3-5일 정도 소요됩니다. 추적번호로 실시간 배송상태를 확인할 수 있습니다.",
      "intent": "order_status",
      "metadata": null,
      "created_at": "2025-12-26T10:30:30"
    }
  ]
}
```

---

### 2.2.4 메시지 전송 (핵심 API)

```
POST /conversations/{conversation_id}/messages
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "content": "환불 정책 알려주세요",
  "metadata": {
    "source": "mobile"
  }
}
```

**Response (200 OK) - 정책 질문:**
```json
{
  "conversation_id": "conv_1735198200123",
  "response": "환불 정책에 대해 안내드립니다.\n\n상품 수령 후 7일 이내에 환불 신청이 가능합니다. 단, 상품이 미개봉 상태여야 하며, 택 제거 시 환불이 불가능합니다.\n\n더 자세한 사항이 궁금하시면 말씀해 주세요.",
  "intent": "policy",
  "message_id": "msg_003",
  "data": {
    "hits": [
      {
        "id": "policy_001",
        "score": 0.95,
        "text": "환불 정책: 상품 수령 후 7일 이내 환불 신청 가능. 미개봉 상태 필수.",
        "metadata": {
          "category": "refund",
          "updated": "2025-12-01"
        }
      }
    ]
  }
}
```

**Response (200 OK) - 주문 조회:**
```json
{
  "conversation_id": "conv_1735198200123",
  "response": "최근 주문 내역입니다.\n\n1. ORD-20251201-001 (배송완료)\n   - 무선 이어폰 x 1\n   - 49,900원\n\n2. ORD-20251125-003 (배송완료)\n   - 블루투스 스피커 x 1\n   - 89,900원",
  "intent": "order",
  "sub_intent": "list",
  "message_id": "msg_004",
  "data": {
    "orders": [
      {
        "order_id": "ORD-20251201-001",
        "status": "delivered",
        "order_date": "2025-12-01T10:30:00Z",
        "total_amount": "49900"
      },
      {
        "order_id": "ORD-20251125-003",
        "status": "delivered",
        "order_date": "2025-11-25T14:15:00Z",
        "total_amount": "89900"
      }
    ]
  }
}
```

**curl 예시:**
```bash
curl -X POST "http://localhost:8000/conversations/conv_1735198200123/messages" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "content": "환불 정책 알려주세요"
  }'
```

---

### 2.2.5 대화 종료

```
DELETE /conversations/{conversation_id}
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "message": "대화가 종료되었습니다"
}
```

---

## 2.3 정책 검색 API

### 2.3.1 정책 검색

```
GET /policies/search?q={query}&top_k={top_k}
Authorization: Bearer {access_token}
```

**Query Parameters:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|-------|------|
| `q` | string | (필수) | 검색어 |
| `top_k` | int | 5 | 반환할 결과 개수 |

**Response (200 OK):**
```json
{
  "query": "환불",
  "hits": [
    {
      "id": "policy_001",
      "score": 0.98,
      "text": "환불 정책: 상품 수령 후 7일 이내 환불 신청 가능합니다. 미개봉 상태여야 하며 택 제거 시 환불이 불가능합니다.",
      "metadata": {
        "category": "refund",
        "updated": "2025-12-01",
        "version": "1.0"
      }
    },
    {
      "id": "policy_005",
      "score": 0.85,
      "text": "환불 절차: 1) 고객센터 연락 2) 반품 신청 3) 상품 반송 4) 확인 후 환불 처리",
      "metadata": {
        "category": "refund_process",
        "updated": "2025-11-15"
      }
    },
    {
      "id": "policy_010",
      "score": 0.72,
      "text": "환불 수수료: 배송료 반품 시 편도 배송료 3,000원 차감",
      "metadata": {
        "category": "refund_fee",
        "updated": "2025-10-20"
      }
    }
  ]
}
```

**curl 예시:**
```bash
curl -X GET "http://localhost:8000/policies/search?q=환불&top_k=3" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## 2.4 주문 API

### 2.4.1 주문 목록 조회

```
GET /users/{user_id}/orders?status={status}&limit={limit}
Authorization: Bearer {access_token}
```

**Query Parameters:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|-------|------|
| `status` | string | - | `pending`, `confirmed`, `shipping`, `delivered`, `cancelled` |
| `limit` | int | 10 | 최대 개수 |

**Response (200 OK):**
```json
{
  "orders": [
    {
      "order_id": "ORD-20251201-001",
      "user_id": "user_a1b2c3d4e5f6",
      "status": "delivered",
      "order_date": "2025-12-01T10:30:00Z",
      "delivery_date": "2025-12-05T15:20:00Z",
      "total_amount": "49900",
      "shipping_address": "서울시 강남구 테헤란로 123"
    },
    {
      "order_id": "ORD-20251125-003",
      "user_id": "user_a1b2c3d4e5f6",
      "status": "delivered",
      "order_date": "2025-11-25T14:15:00Z",
      "delivery_date": "2025-11-28T10:45:00Z",
      "total_amount": "89900",
      "shipping_address": "서울시 강남구 테헤란로 123"
    }
  ]
}
```

---

### 2.4.2 주문 상세 조회

```
GET /orders/{order_id}
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "order": {
    "order_id": "ORD-20251201-001",
    "user_id": "user_a1b2c3d4e5f6",
    "status": "delivered",
    "order_date": "2025-12-01T10:30:00Z",
    "delivery_date": "2025-12-05T15:20:00Z",
    "total_amount": "49900",
    "shipping_address": "서울시 강남구 테헤란로 123"
  },
  "items": [
    {
      "id": "item_001",
      "order_id": "ORD-20251201-001",
      "product_id": "prod_123",
      "quantity": 1,
      "unit_price": "49900",
      "title": "무선 이어폰",
      "brand": "TechBrand",
      "price": "49900",
      "image_url": "https://example.com/images/earbuds.jpg"
    }
  ]
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "order not found"
}
```

---

### 2.4.3 주문 상태 조회

```
GET /orders/{order_id}/status
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "status": {
    "order_id": "ORD-20251201-001",
    "status": "shipping",
    "estimated_delivery": "2025-12-05T00:00:00"
  }
}
```

---

### 2.4.4 주문 취소

```
POST /orders/{order_id}/cancel
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "reason": "단순 변심"
}
```

**Response (200 OK) - 취소 성공:**
```json
{
  "ok": true,
  "order_id": "ORD-20251201-001",
  "status": "cancelled",
  "reason": "단순 변심"
}
```

**Response (200 OK) - 취소 불가:**
```json
{
  "ok": false,
  "order_id": "ORD-20251201-001",
  "status": "shipping",
  "error": "Cancellable only before shipping"
}
```

---

## 2.5 티켓 API

### 2.5.1 티켓 생성

```
POST /tickets
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "user_id": "user_a1b2c3d4e5f6",
  "order_id": "ORD-20251201-001",
  "issue_type": "refund",
  "description": "상품 불량으로 환불 요청합니다.",
  "priority": "normal"
}
```

**Response (201 Created):**
```json
{
  "ticket": {
    "ticket_id": "TICKET-1735198200",
    "user_id": "user_a1b2c3d4e5f6",
    "order_id": "ORD-20251201-001",
    "issue_type": "refund",
    "description": "상품 불량으로 환불 요청합니다.",
    "status": "open",
    "priority": "normal",
    "created_at": "2025-12-26T10:30:00Z",
    "resolved_at": ""
  }
}
```

**Error Response (422 Validation Error):**
```json
{
  "detail": [
    {
      "loc": ["body", "description"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### 2.5.2 티켓 조회

```
GET /tickets/{ticket_id}
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "ticket": {
    "ticket_id": "TICKET-1735198200",
    "user_id": "user_a1b2c3d4e5f6",
    "order_id": "ORD-20251201-001",
    "issue_type": "refund",
    "description": "상품 불량으로 환불 요청합니다.",
    "status": "open",
    "priority": "normal",
    "created_at": "2025-12-26T10:30:00Z",
    "resolved_at": ""
  }
}
```

---

### 2.5.3 사용자 티켓 목록

```
GET /users/{user_id}/tickets?status={status}&limit={limit}
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "tickets": [
    {
      "ticket_id": "TICKET-1735198200",
      "user_id": "user_a1b2c3d4e5f6",
      "order_id": "ORD-20251201-001",
      "issue_type": "refund",
      "description": "상품 불량으로 환불 요청합니다.",
      "status": "open",
      "priority": "normal",
      "created_at": "2025-12-26T10:30:00Z",
      "resolved_at": ""
    }
  ]
}
```

---

### 2.5.4 티켓 해결

```
POST /tickets/{ticket_id}/resolve
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "ticket": {
    "ticket_id": "TICKET-1735198200",
    "user_id": "user_a1b2c3d4e5f6",
    "order_id": "ORD-20251201-001",
    "issue_type": "refund",
    "description": "상품 불량으로 환불 요청합니다.",
    "status": "resolved",
    "priority": "normal",
    "created_at": "2025-12-26T10:30:00Z",
    "resolved_at": "2025-12-26T14:45:00Z"
  }
}
```

---

## 2.6 채팅 API

### 2.6.1 단순 채팅

```
POST /chat
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "user_id": "user_a1b2c3d4e5f6",
  "message": "환불 정책 알려주세요"
}
```

**Response (200 OK):**
```json
{
  "response": "환불 정책에 따르면, 상품 수령 후 7일 이내에 환불을 신청할 수 있습니다. 미개봉 상태여야 합니다.",
  "intent": "policy",
  "sub_intent": null,
  "hits": [
    {
      "id": "policy_001",
      "score": 0.98,
      "text": "환불 정책: ...",
      "metadata": {
        "category": "refund"
      }
    }
  ]
}
```

---

### 2.6.2 스트리밍 채팅

```
POST /chat/stream
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "message": "배송은 얼마나 걸려요?",
  "system_prompt": "당신은 친절한 고객 서비스 담당자입니다."
}
```

**Response (200 OK - Server-Sent Events):**
```
data: 배
data: 송
data: 은
data:  보
data: 통
data:  3
data: -
data: 5
data: 일
data:  정
data: 도
data:  소
data: 요
data: 됩
data: 니
data: 다
data: .
data: [DONE]
```

---

## 2.7 헬스체크 API

### 2.7.1 Liveness Check

```
GET /healthz
```

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### 2.7.2 상세 헬스체크

```
GET /health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "components": {
    "database": {
      "status": "up"
    },
    "rag_index": {
      "status": "up",
      "documents": 2456
    }
  }
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "components": {
    "database": {
      "status": "down",
      "error": "Connection refused"
    }
  }
}
```

---

### 2.7.3 Readiness Check

```
GET /ready
```

**Response (200 OK):**
```json
{
  "status": "ready"
}
```

**Response (503 Service Unavailable):**
```json
{
  "detail": "Database not ready"
}
```

---

### 2.7.4 Prometheus 메트릭

```
GET /metrics
```

**Response (200 OK - text/plain):**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/policies/search",status="200"} 1234.0
http_requests_total{method="POST",endpoint="/chat",status="200"} 567.0
http_requests_total{method="GET",endpoint="/health",status="200"} 890.0

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",endpoint="/policies/search",le="0.01"} 100.0
http_request_duration_seconds_bucket{method="GET",endpoint="/policies/search",le="0.05"} 800.0
http_request_duration_seconds_bucket{method="GET",endpoint="/policies/search",le="0.1"} 1000.0
http_request_duration_seconds_bucket{method="GET",endpoint="/policies/search",le="+Inf"} 1234.0
```

---

# 3장: 내부 데이터 흐름

이 장에서는 사용자 메시지가 시스템 내부에서 어떻게 처리되는지 단계별로 설명합니다.

## 3.1 데이터 구조 정의

### 3.1.1 IntentResult (의도 분류 결과)

**파일**: `src/agents/nodes/intent_classifier.py`

```python
@dataclass
class IntentResult:
    intent: str              # "order", "claim", "policy", "general", "unknown"
    sub_intent: Optional[str] # "list", "status", "detail", "cancel" (order만)
    payload: Dict[str, Any]  # 의도별 추출된 파라미터
    confidence: str = "high" # "low", "medium", "high"
    source: str = "keyword"  # "keyword" 또는 "llm"
    reason: str = ""         # 분류 이유
```

**샘플 데이터:**

```python
# 정책 질문
IntentResult(
    intent="policy",
    sub_intent=None,
    payload={
        "query": "환불 정책 알려주세요",
        "top_k": 5
    },
    confidence="high",
    source="keyword",
    reason="키워드 '환불', '정책' 감지"
)

# 주문 목록 조회
IntentResult(
    intent="order",
    sub_intent="list",
    payload={
        "limit": 10,
        "status": None,
        "include_items": False
    },
    confidence="high",
    source="keyword",
    reason="키워드 '주문', '보여줘' 감지"
)

# 주문 취소
IntentResult(
    intent="order",
    sub_intent="cancel",
    payload={
        "order_id": "ORD-20251201-001",
        "reason": "단순 변심"
    },
    confidence="high",
    source="keyword",
    reason="키워드 '취소', 주문번호 패턴 감지"
)

# 클레임 접수
IntentResult(
    intent="claim",
    sub_intent=None,
    payload={
        "action": "create",
        "order_id": "ORD-20251201-001",
        "issue_type": "defect",
        "description": "상품이 불량이에요",
        "priority": "normal"
    },
    confidence="high",
    source="keyword",
    reason="키워드 '불량' 감지"
)
```

---

### 3.1.2 AgentContext (에이전트 컨텍스트)

**파일**: `src/agents/router.py`

```python
@dataclass
class AgentContext:
    user_id: str                              # 사용자 ID
    message: str                              # 원본 사용자 메시지
    intent: str                               # 분류된 의도
    sub_intent: str                           # 세부 의도
    entities: Dict[str, Any]                  # 추출된 엔티티 (= payload)
    history: List[Dict[str, str]] = field(default_factory=list)  # 대화 기록
    metadata: Dict[str, Any] = field(default_factory=dict)       # 메타데이터
```

**샘플 데이터:**

```python
AgentContext(
    user_id="user_a1b2c3d4e5f6",
    message="ORD-20251201-001 주문 취소해줘",
    intent="order",
    sub_intent="cancel",
    entities={
        "order_id": "ORD-20251201-001",
        "reason": "사용자 요청"
    },
    history=[
        {"role": "user", "content": "주문 내역 보여줘"},
        {"role": "assistant", "content": "최근 주문 내역입니다..."}
    ],
    metadata={
        "conversation_id": "conv_1735198200123",
        "source": "mobile"
    }
)
```

---

### 3.1.3 AgentResponse (에이전트 응답)

**파일**: `src/agents/specialists/base.py`

```python
@dataclass
class AgentResponse:
    success: bool                             # 처리 성공 여부
    message: str                              # 사용자에게 보여줄 응답
    data: Dict[str, Any]                      # 구조화된 데이터
    suggested_actions: List[str] = field(default_factory=list)   # 추천 액션
    requires_escalation: bool = False         # 상담원 연결 필요 여부
    escalation_reason: str = ""               # 에스컬레이션 사유
```

**샘플 데이터:**

```python
# 정책 검색 응답
AgentResponse(
    success=True,
    message="환불 정책에 대해 안내드립니다.\n\n상품 수령 후 7일 이내에 환불 신청이 가능합니다.",
    data={
        "hits": [
            {
                "id": "policy_001",
                "score": 0.95,
                "text": "환불 정책: 상품 수령 후 7일 이내...",
                "metadata": {"category": "refund"}
            }
        ],
        "query": "환불 정책 알려주세요"
    },
    suggested_actions=["환불 신청하기", "교환 정책 보기"]
)

# 주문 취소 응답
AgentResponse(
    success=True,
    message="주문이 성공적으로 취소되었습니다.",
    data={
        "cancel_result": {
            "ok": True,
            "order_id": "ORD-20251201-001",
            "status": "cancelled"
        }
    },
    suggested_actions=["다른 상품 보기", "장바구니 확인"]
)

# 에스컬레이션 필요 응답
AgentResponse(
    success=False,
    message="죄송합니다. 해당 문의는 상담원 연결이 필요합니다.",
    data={},
    requires_escalation=True,
    escalation_reason="복잡한 환불 요청 - 상담원 판단 필요"
)
```

---

### 3.1.4 AgentState (상태 관리)

**파일**: `src/agents/state.py`

```python
@dataclass
class AgentState:
    user_id: str                              # 사용자 ID
    intent: str                               # 의도
    sub_intent: Optional[str] = None          # 세부 의도
    payload: Dict[str, Any] = field(default_factory=dict)        # 파라미터
    final_response: Optional[Dict[str, Any]] = None              # 최종 응답
```

**샘플 데이터:**

```python
# 초기 상태
AgentState(
    user_id="user_a1b2c3d4e5f6",
    intent="order",
    sub_intent="list",
    payload={"limit": 10},
    final_response=None
)

# 처리 완료 후 상태
AgentState(
    user_id="user_a1b2c3d4e5f6",
    intent="order",
    sub_intent="list",
    payload={"limit": 10},
    final_response={
        "response": "최근 주문 내역입니다...",
        "data": {
            "orders": [...]
        },
        "intent": "order",
        "sub_intent": "list"
    }
)
```

---

## 3.2 단계별 데이터 변환

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          데이터 변환 흐름도                                    │
└──────────────────────────────────────────────────────────────────────────────┘

 사용자 입력                     의도 분류                    라우팅
┌─────────────┐             ┌─────────────────┐         ┌─────────────────┐
│             │             │                 │         │                 │
│   "환불     │  ────────▶  │  IntentResult   │ ──────▶ │  AgentContext   │
│   정책      │  classify_  │  intent=policy  │ create_ │  intent=policy  │
│   알려주세요" │  intent()   │  payload={...}  │ context │  entities={...} │
│             │             │                 │         │                 │
└─────────────┘             └─────────────────┘         └─────────────────┘
                                                                │
                                                                ▼
 최종 응답                   오케스트레이터                  전문가 처리
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│                 │         │                 │         │                 │
│  final_response │ ◀────── │  Orchestrator   │ ◀────── │ AgentResponse   │
│  {              │ build_  │  LLM 호출       │ handle()│ success=True    │
│    "response":  │ response│  가드레일 적용   │         │ message="..."   │
│    "data": {}   │         │                 │         │ data={...}      │
│  }              │         │                 │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 변환 단계 요약

| 단계 | 입력 | 함수 | 출력 |
|------|------|------|------|
| 1 | `str` (메시지) | `classify_intent()` | `IntentResult` |
| 2 | `IntentResult` | `create_context()` | `AgentContext` |
| 3 | `AgentContext` | `specialist.handle()` | `AgentResponse` |
| 4 | `AgentResponse` | `build_response()` | `final_response` |

---

## 3.3 입력 가드레일 상세 흐름

의도 분류 **이전**에 4단계 입력 검증이 수행됩니다.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         입력 가드레일 처리 파이프라인                           │
└──────────────────────────────────────────────────────────────────────────────┘

 사용자 입력
┌─────────────────────────────────────────────────────────────────────────────┐
│  "제 휴대폰 010-1234-5678로 연락주세요. 주문 취소해주세요."                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: 길이 검증                                                            │
│ ────────────────────────────────────────────────────────────────────────────│
│ - min_input_length: 1자                                                     │
│ - max_input_length: 2000자                                                  │
│ - 초과 시: InputGuardResult(blocked=True, block_reason="메시지가 너무 깁니다")│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ ✅ 통과
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: PII 탐지 및 마스킹                                                   │
│ ────────────────────────────────────────────────────────────────────────────│
│ 탐지 패턴:                                                                   │
│   - 휴대폰: 010-1234-5678 → [전화번호]                                       │
│   - 이메일: user@example.com → [이메일]                                      │
│   - 주민번호: 901201-1234567 → [주민번호]                                    │
│   - 카드번호: 1234-5678-9012-3456 → [카드번호]                               │
│                                                                             │
│ 결과:                                                                        │
│   sanitized_text: "제 휴대폰 [전화번호]로 연락주세요. 주문 취소해주세요."       │
│   pii_detected: [{"type": "phone", "value": "010-1234-5678", "masked": true}]│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ ✅ 마스킹 적용
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: 프롬프트 인젝션 탐지                                                  │
│ ────────────────────────────────────────────────────────────────────────────│
│ 탐지 패턴:                                                                   │
│   - "ignore previous instructions"                                          │
│   - "system prompt"                                                         │
│   - "you are now"                                                           │
│   - "disregard"                                                             │
│                                                                             │
│ strict_mode=True:                                                           │
│   - 탐지 시 blocked=True, block_reason="잠재적 보안 위협 감지"               │
│ strict_mode=False:                                                          │
│   - 탐지 시 warnings에 추가, 처리 계속                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ ✅ 인젝션 없음
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: 금지어 탐지                                                          │
│ ────────────────────────────────────────────────────────────────────────────│
│ 탐지 대상: configs/guardrails.yaml의 forbidden_words 목록                    │
│                                                                             │
│ strict_mode=True:                                                           │
│   - 탐지 시 blocked=True                                                    │
│ strict_mode=False:                                                          │
│   - 탐지 시 warnings에 추가                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ ✅ 금지어 없음
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ InputGuardResult 반환                                                        │
│ ────────────────────────────────────────────────────────────────────────────│
│ {                                                                           │
│   "ok": true,                                                               │
│   "blocked": false,                                                         │
│   "sanitized_text": "제 휴대폰 [전화번호]로 연락주세요. 주문 취소해주세요.",    │
│   "pii_detected": [{"type": "phone", ...}],                                 │
│   "warnings": [],                                                           │
│   "block_reason": null                                                      │
│ }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          IntentClassifier로 전달
                          (마스킹된 텍스트 사용)
```

### InputGuardResult 구조

```python
@dataclass
class InputGuardResult:
    ok: bool                          # 전체 검증 성공 여부
    blocked: bool                     # 차단 여부
    sanitized_text: str               # PII 마스킹된 텍스트
    pii_detected: List[Dict]          # 탐지된 PII 목록
    warnings: List[str]               # 경고 메시지
    block_reason: Optional[str]       # 차단 사유
```

---

## 3.4 출력 가드레일 상세 흐름

LLM 응답 생성 **이후** 5단계 출력 검증이 수행됩니다.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         출력 가드레일 처리 파이프라인                           │
└──────────────────────────────────────────────────────────────────────────────┘

 LLM 응답
┌─────────────────────────────────────────────────────────────────────────────┐
│  "환불 정책에 대해 안내드립니다. 고객님 연락처 010-9999-8888로..."              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: 가격/재고 검증 (validate_price_stock)                                │
│ ────────────────────────────────────────────────────────────────────────────│
│ - 응답에 언급된 가격이 CSV 저장소의 실제 가격과 일치하는지 확인                 │
│ - 재고 정보가 정확한지 검증                                                   │
│ - 불일치 시 warnings에 추가                                                  │
│                                                                             │
│ 결과: {"mismatches": [], "warnings": []}                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: 정책 준수 체크 (check_policy_compliance)                             │
│ ────────────────────────────────────────────────────────────────────────────│
│ 위반 패턴 검사:                                                              │
│   - "환불 기간 30일 초과" 언급                                               │
│   - "100% 환불 약속" (실제 정책과 다를 수 있음)                               │
│   - "즉시 처리 약속" (처리 시간 보장 불가)                                    │
│                                                                             │
│ 정책 키워드 탐지:                                                            │
│   - 환불, 교환, 배송, 취소 관련 표현 정합성 확인                              │
│                                                                             │
│ 결과: {"violations": [], "keywords_found": ["환불", "정책"]}                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: PII/민감 정보 마스킹 (apply_output_guards)                           │
│ ────────────────────────────────────────────────────────────────────────────│
│ 입력 가드레일과 동일한 패턴으로 응답 내 PII 마스킹                             │
│                                                                             │
│ 변환:                                                                        │
│   Before: "고객님 연락처 010-9999-8888로..."                                 │
│   After:  "고객님 연락처 [전화번호]로..."                                     │
│                                                                             │
│ 결과: {"modified": true, "modifications": ["phone_masked"]}                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: 부적절한 내용 탐지                                                   │
│ ────────────────────────────────────────────────────────────────────────────│
│ - 욕설, 비속어 탐지                                                          │
│ - 경쟁사 언급 탐지                                                           │
│ - 부정확한 약속 표현 탐지                                                    │
│                                                                             │
│ 결과: {"inappropriate": [], "warnings": []}                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 5: 톤 검증 (존댓말 비율)                                                │
│ ────────────────────────────────────────────────────────────────────────────│
│ - min_polite_ratio: 0.7 (70% 이상 존댓말 사용 필요)                          │
│ - 문장별 존댓말 여부 판단                                                    │
│ - 비율 미달 시 warnings에 추가                                              │
│                                                                             │
│ 결과: {"polite_ratio": 0.85, "ok": true}                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 최종 응답 + guard 정보                                                       │
│ ────────────────────────────────────────────────────────────────────────────│
│ {                                                                           │
│   "response": "환불 정책에 대해 안내드립니다. 고객님 연락처 [전화번호]로...",   │
│   "data": {...},                                                            │
│   "guard": {                                                                │
│     "price_stock": {"mismatches": []},                                      │
│     "policy": {"violations": []},                                           │
│     "output": {"ok": true, "modified": true},                               │
│     "tone": {"polite_ratio": 0.85}                                          │
│   }                                                                         │
│ }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3.5 LLM 라우팅 폴백 메커니즘

LLM 호출은 3가지 경로로 분기됩니다.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         LLM 라우팅 폴백 흐름                                   │
└──────────────────────────────────────────────────────────────────────────────┘

 에이전트 처리 완료 (AgentResponse)
                    │
                    ▼
          ┌─────────────────┐
          │ use_llm 설정?   │
          │ (API 키 존재?)  │
          └────────┬────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
    use_llm=True        use_llm=False
         │                   │
         ▼                   ▼
┌─────────────────┐  ┌─────────────────────┐
│ generate_       │  │ apply_guards(data)  │
│ routed_response │  │ (LLM 없이 데이터만) │
│ 존재?           │  └─────────────────────┘
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
  있음       없음
    │         │
    ▼         ▼
┌──────────────────┐  ┌──────────────────┐
│ 경로 1:          │  │ 경로 2:          │
│ generate_        │  │ generate_        │
│ routed_response  │  │ response         │
│ (의도별 라우팅)   │  │ (기본 LLM)       │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         └──────────┬──────────┘
                    │
                    ▼
           ┌───────────────┐
           │ LLM 호출 성공? │
           └───────┬───────┘
                   │
         ┌─────────┴─────────┐
         │                   │
       성공                실패
         │                   │
         ▼                   ▼
┌─────────────────────┐  ┌─────────────────────┐
│ apply_guards(       │  │ 경로 3:             │
│   response=llm_text,│  │ apply_guards(data)  │
│   data=data         │  │ (폴백: 데이터만)    │
│ )                   │  │                     │
└─────────────────────┘  │ 로그: "LLM 응답     │
                         │ 생성 실패, 기본     │
                         │ 응답 사용"          │
                         └─────────────────────┘
```

### 라우팅 결정 로직

```python
# 경로 결정 순서
if not use_llm:
    # 경로 3: LLM 미사용 → 데이터만 반환
    return apply_guards(data)

try:
    if generate_routed_response:
        # 경로 1: 의도별 라우팅 LLM 사용
        llm_response = await generate_routed_response(...)
    else:
        # 경로 2: 기본 LLM 사용
        llm_response = await generate_response(...)

    return apply_guards({"response": llm_response, "data": data})

except Exception as e:
    # 경로 3: LLM 실패 → 폴백
    logger.warning(f"LLM 응답 생성 실패: {e}")
    return apply_guards(data)
```

---

## 3.6 RAG 검색 및 리랭킹 폴백

하이브리드 검색과 리랭킹에도 폴백 메커니즘이 있습니다.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         RAG 검색 파이프라인 상세                               │
└──────────────────────────────────────────────────────────────────────────────┘

 검색 쿼리: "환불 정책"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: 병렬 검색 (Hybrid Search)                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────┐         ┌───────────────────────┐               │
│  │ 키워드 검색           │         │ 벡터 검색             │               │
│  │ (TF-IDF/BM25)        │         │ (FAISS + E5 임베딩)   │               │
│  │                       │         │                       │               │
│  │ fetch_k = top_k * 3  │         │ fetch_k = top_k * 3  │               │
│  └───────────┬───────────┘         └───────────┬───────────┘               │
│              │                                  │                           │
│              └──────────────┬───────────────────┘                           │
│                             ▼                                               │
│              ┌─────────────────────────────┐                                │
│              │ 가중치 합산 (Score Fusion)  │                                │
│              │                             │                                │
│              │ hybrid_alpha = 0.5 (기본값) │                                │
│              │                             │                                │
│              │ 키워드 점수 * (1 - alpha)   │                                │
│              │ + 벡터 점수 * alpha         │                                │
│              └─────────────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: 리랭킹 (Reranking)                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     외부 리랭커 시도                                    │  │
│  │                  (Cross-Encoder 모델)                                  │  │
│  └───────────────────────────────┬───────────────────────────────────────┘  │
│                                  │                                          │
│                    ┌─────────────┴─────────────┐                            │
│                    │                           │                            │
│                  성공                        실패                           │
│                    │                           │                            │
│                    ▼                           ▼                            │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────────┐│
│  │ Cross-Encoder 점수로   │    │ 휴리스틱 리랭커 (Fallback)              ││
│  │ 재정렬                  │    │                                         ││
│  │                         │    │ score = (쿼리 토큰 ∩ 본문 토큰)         ││
│  │                         │    │       + 2.0 * (쿼리 토큰 ∩ 제목 토큰)   ││
│  │                         │    │       + 0.1 * 원래_점수                 ││
│  └─────────────────────────┘    └─────────────────────────────────────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
           상위 top_k개 반환
```

### 휴리스틱 리랭커 로직

```python
def _heuristic_rerank(self, query: str, hits: List[Hit]) -> List[Hit]:
    """외부 리랭커 실패 시 폴백"""
    q_tokens = set(query.lower().split())

    scored = []
    for hit in hits:
        text_tokens = set(hit.text.lower().split())
        title = hit.metadata.get("title", "")
        title_tokens = set(title.lower().split()) if title else set()

        # 본문 토큰 겹침 + 제목 가중치 2배 + 원래 점수 10%
        score = (
            len(q_tokens & text_tokens)
            + 2.0 * len(q_tokens & title_tokens)
            + 0.1 * hit.score
        )
        scored.append((score, hit))

    # 점수 내림차순 정렬
    scored.sort(key=lambda x: x[0], reverse=True)
    return [hit for _, hit in scored]
```

---

## 3.7 대화 히스토리 자동 구성

멀티턴 대화에서 히스토리가 자동으로 관리됩니다.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         대화 히스토리 관리                                    │
└──────────────────────────────────────────────────────────────────────────────┘

 Conversation 객체
┌─────────────────────────────────────────────────────────────────────────────┐
│ messages: [                                                                 │
│   {role: "user",      content: "안녕하세요"},           # 오래된 메시지     │
│   {role: "assistant", content: "안녕하세요! 무엇을..."}, # ↑               │
│   {role: "user",      content: "주문 내역 보여줘"},      #                  │
│   {role: "assistant", content: "최근 주문입니다..."},    #                  │
│   ...                                                    #                  │
│   {role: "user",      content: "환불 정책 알려줘"},      # ↓               │
│   {role: "assistant", content: "환불 정책은..."},        # 최신 메시지     │
│ ]                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    │ get_history_for_llm(max_messages=10)
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LLM에 전달되는 히스토리 (최신 10개만)                                        │
│ ────────────────────────────────────────────────────────────────────────────│
│ [                                                                           │
│   {"role": "user", "content": "..."},       # messages[-10]                │
│   {"role": "assistant", "content": "..."},  # messages[-9]                 │
│   ...                                                                       │
│   {"role": "user", "content": "환불 정책 알려줘"},      # messages[-2]      │
│   {"role": "assistant", "content": "환불 정책은..."},   # messages[-1]      │
│ ]                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

 설정:
   - max_history_messages: 10 (기본값)
   - 최신 메시지부터 역순으로 선택
   - 메시지는 {role, content} 형태로 변환
```

---

## 3.8 에이전트 라우터 폴백 체인

의도에 맞는 에이전트가 없을 때의 폴백 로직입니다.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         에이전트 라우터 폴백 체인                              │
└──────────────────────────────────────────────────────────────────────────────┘

 intent = "unknown"
                    │
                    ▼
          ┌─────────────────┐
          │ 1. 정확히 매칭  │
          │ agents[intent]  │
          └────────┬────────┘
                   │
              없음 │
                   ▼
          ┌─────────────────┐
          │ 2. Policy 폴백  │
          │ agents["policy"]│
          └────────┬────────┘
                   │
              없음 │
                   ▼
          ┌─────────────────┐
          │ 3. General 폴백 │
          │ agents["general"]│
          └────────┬────────┘
                   │
              없음 │
                   ▼
          ┌─────────────────┐
          │ 4. 에러 응답    │
          │ AgentResponse(  │
          │   success=False,│
          │   message="..." │
          │ )               │
          └─────────────────┘
```

```python
def get_agent(self, intent: str) -> Optional[BaseAgent]:
    """의도에 맞는 에이전트 반환 (폴백 포함)"""
    # 1. 정확히 매칭
    agent = self._agents.get(intent)
    if agent:
        return agent

    # 2. Policy 폴백 (unknown → policy)
    if intent == "unknown":
        agent = self._agents.get("policy")
        if agent:
            return agent

    # 3. General 폴백
    agent = self._agents.get("general")
    if agent:
        return agent

    # 4. 없으면 None
    return None
```

---

# 4장: End-to-End 시나리오

이 장에서는 실제 사용자 질문이 시스템을 통과하는 전체 과정을 단계별로 추적합니다.

## 4.1 시나리오 1: 정책 질문

**사용자 입력**: `"환불 정책 알려주세요"`

### Step 1: 의도 분류

```python
# 입력
message = "환불 정책 알려주세요"

# 키워드 분석
keywords_detected = ["환불", "정책"]  # configs/intents.yaml의 policy 패턴 매칭

# 출력: IntentResult
IntentResult(
    intent="policy",
    sub_intent=None,
    payload={
        "query": "환불 정책 알려주세요",
        "top_k": 5
    },
    confidence="high",
    source="keyword",
    reason="키워드 '환불', '정책' 감지"
)
```

### Step 2: 컨텍스트 생성

```python
# IntentResult → AgentContext 변환
AgentContext(
    user_id="user_a1b2c3d4e5f6",
    message="환불 정책 알려주세요",
    intent="policy",
    sub_intent="",
    entities={
        "query": "환불 정책 알려주세요",
        "top_k": 5
    },
    history=[],
    metadata={
        "conversation_id": "conv_1735198200123"
    }
)
```

### Step 3: PolicySpecialist 처리

```python
# RAG 검색 실행
search_results = retriever.search(
    query="환불 정책 알려주세요",
    top_k=5,
    mode="hybrid"  # 키워드 + 벡터 검색
)

# 검색 결과
hits = [
    Hit(
        id="policy_001",
        score=0.95,
        text="환불 정책: 상품 수령 후 7일 이내 환불 신청 가능...",
        metadata={"category": "refund"}
    ),
    Hit(
        id="policy_005",
        score=0.82,
        text="환불 절차: 1) 고객센터 연락...",
        metadata={"category": "refund_process"}
    )
]

# LLM 응답 생성
llm_response = await generate_response(
    system_prompt="한국어 전자상거래 고객 상담 에이전트입니다...",
    context=hits,
    user_message="환불 정책 알려주세요"
)

# 출력: AgentResponse
AgentResponse(
    success=True,
    message="환불 정책에 대해 안내드립니다.\n\n상품 수령 후 7일 이내에 환불 신청이 가능합니다. 단, 상품이 미개봉 상태여야 하며, 택 제거 시 환불이 불가능합니다.\n\n더 자세한 사항이 궁금하시면 말씀해 주세요.",
    data={
        "hits": [
            {"id": "policy_001", "score": 0.95, "text": "...", "metadata": {...}},
            {"id": "policy_005", "score": 0.82, "text": "...", "metadata": {...}}
        ],
        "query": "환불 정책 알려주세요"
    },
    suggested_actions=["환불 신청하기", "교환 정책 보기"]
)
```

### Step 4: 최종 응답 생성

```python
# 가드레일 적용
guarded_message = apply_output_guards(agent_response.message)
# - PII 마스킹 확인
# - 금지어 필터링
# - 톤/매너 검증

# 최종 응답
final_response = {
    "conversation_id": "conv_1735198200123",
    "response": "환불 정책에 대해 안내드립니다.\n\n상품 수령 후 7일 이내에 환불 신청이 가능합니다. 단, 상품이 미개봉 상태여야 하며, 택 제거 시 환불이 불가능합니다.\n\n더 자세한 사항이 궁금하시면 말씀해 주세요.",
    "intent": "policy",
    "message_id": "msg_003",
    "data": {
        "hits": [
            {"id": "policy_001", "score": 0.95, "text": "...", "metadata": {...}}
        ]
    }
}
```

### 전체 흐름 다이어그램

```
"환불 정책 알려주세요"
        │
        ▼
┌───────────────────────┐
│ IntentClassifier      │
│ ─────────────────────  │
│ intent: "policy"      │
│ payload.query: "..."  │
│ confidence: "high"    │
│ source: "keyword"     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ AgentRouter           │
│ ─────────────────────  │
│ → PolicySpecialist    │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ PolicySpecialist      │
│ ─────────────────────  │
│ 1. RAG 검색           │
│    - 임베딩 생성      │
│    - FAISS 검색       │
│    - 하이브리드 스코어 │
│                       │
│ 2. LLM 응답 생성      │
│    - 컨텍스트 주입    │
│    - 프롬프트 구성    │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Output Guardrail      │
│ ─────────────────────  │
│ - PII 마스킹 확인     │
│ - 금지어 필터링       │
│ - 톤/매너 검증        │
└───────────┬───────────┘
            │
            ▼
{
  "response": "환불 정책에 대해...",
  "intent": "policy",
  "data": {"hits": [...]}
}
```

---

## 4.2 시나리오 2: 주문 목록 조회

**사용자 입력**: `"최근 주문 보여줘"`

### Step 1: 의도 분류

```python
IntentResult(
    intent="order",
    sub_intent="list",
    payload={
        "limit": 10,
        "status": None,
        "include_items": False
    },
    confidence="high",
    source="keyword",
    reason="키워드 '주문', '보여줘' 감지"
)
```

### Step 2: OrderSpecialist 처리

```python
# 주문 서비스 호출
orders = await order_service.get_user_orders(
    user_id="user_a1b2c3d4e5f6",
    limit=10,
    status=None
)

# 조회 결과
orders = [
    {
        "order_id": "ORD-20251201-001",
        "status": "delivered",
        "order_date": "2025-12-01T10:30:00Z",
        "total_amount": "49900"
    },
    {
        "order_id": "ORD-20251125-003",
        "status": "delivered",
        "order_date": "2025-11-25T14:15:00Z",
        "total_amount": "89900"
    }
]

# LLM 응답 생성
AgentResponse(
    success=True,
    message="최근 주문 내역입니다.\n\n1. ORD-20251201-001 (배송완료)\n   - 49,900원\n\n2. ORD-20251125-003 (배송완료)\n   - 89,900원",
    data={
        "orders": orders
    },
    suggested_actions=["ORD-20251201-001 상세보기", "ORD-20251125-003 상세보기"]
)
```

### Step 3: 최종 응답

```json
{
  "conversation_id": "conv_1735198200123",
  "response": "최근 주문 내역입니다.\n\n1. ORD-20251201-001 (배송완료)\n   - 49,900원\n\n2. ORD-20251125-003 (배송완료)\n   - 89,900원",
  "intent": "order",
  "sub_intent": "list",
  "message_id": "msg_004",
  "data": {
    "orders": [
      {
        "order_id": "ORD-20251201-001",
        "status": "delivered",
        "order_date": "2025-12-01T10:30:00Z",
        "total_amount": "49900"
      },
      {
        "order_id": "ORD-20251125-003",
        "status": "delivered",
        "order_date": "2025-11-25T14:15:00Z",
        "total_amount": "89900"
      }
    ]
  }
}
```

---

## 4.3 시나리오 3: 주문 취소

**사용자 입력**: `"ORD-20251201-001 취소해줘"`

### Step 1: 의도 분류

```python
IntentResult(
    intent="order",
    sub_intent="cancel",
    payload={
        "order_id": "ORD-20251201-001",
        "reason": "사용자 요청"
    },
    confidence="high",
    source="keyword",
    reason="키워드 '취소', 주문번호 패턴 'ORD-\\d{8}-\\d{3}' 감지"
)
```

### Step 2: OrderSpecialist 처리

```python
# 주문 상태 확인
order = await order_service.get_order("ORD-20251201-001")
# order.status = "pending" → 취소 가능

# 취소 실행
cancel_result = await order_service.cancel_order(
    order_id="ORD-20251201-001",
    reason="사용자 요청"
)

# 취소 성공
AgentResponse(
    success=True,
    message="주문이 성공적으로 취소되었습니다.\n\n주문번호: ORD-20251201-001\n취소 사유: 사용자 요청",
    data={
        "cancel_result": {
            "ok": True,
            "order_id": "ORD-20251201-001",
            "status": "cancelled"
        }
    },
    suggested_actions=["다른 상품 보기", "장바구니 확인"]
)
```

### Step 3: 취소 불가 시 응답

```python
# order.status = "shipping" → 취소 불가
AgentResponse(
    success=False,
    message="죄송합니다. 이미 배송 중인 주문은 취소할 수 없습니다.\n\n배송 완료 후 반품 절차를 안내해 드릴까요?",
    data={
        "cancel_result": {
            "ok": False,
            "order_id": "ORD-20251201-001",
            "status": "shipping",
            "error": "Cancellable only before shipping"
        }
    },
    suggested_actions=["반품 절차 안내", "상담원 연결"]
)
```

---

## 4.4 시나리오 4: 클레임 접수

**사용자 입력**: `"상품이 불량이에요"`

### Step 1: 의도 분류

```python
IntentResult(
    intent="claim",
    sub_intent=None,
    payload={
        "action": "create",
        "order_id": None,  # 주문번호 미제공
        "issue_type": "defect",
        "description": "상품이 불량이에요",
        "priority": "normal"
    },
    confidence="high",
    source="keyword",
    reason="키워드 '불량' 감지"
)
```

### Step 2: ClaimSpecialist 처리

```python
# 주문번호가 없으면 최근 주문 조회
recent_orders = await order_service.get_user_orders(
    user_id="user_a1b2c3d4e5f6",
    limit=1
)

# 티켓 생성
ticket = await ticket_service.create_ticket(
    user_id="user_a1b2c3d4e5f6",
    order_id=recent_orders[0]["order_id"],  # 자동 연결
    issue_type="defect",
    description="상품이 불량이에요",
    priority="normal"
)

# 응답 생성
AgentResponse(
    success=True,
    message="불량품 신고가 접수되었습니다.\n\n티켓번호: TICKET-1735198200\n주문번호: ORD-20251201-001\n문제 유형: 상품 불량\n\n담당자가 확인 후 연락드리겠습니다.",
    data={
        "ticket": {
            "ticket_id": "TICKET-1735198200",
            "order_id": "ORD-20251201-001",
            "issue_type": "defect",
            "status": "open"
        }
    },
    suggested_actions=["사진 첨부하기", "반품 절차 안내"]
)
```

### Step 3: 최종 응답

```json
{
  "conversation_id": "conv_1735198200123",
  "response": "불량품 신고가 접수되었습니다.\n\n티켓번호: TICKET-1735198200\n주문번호: ORD-20251201-001\n문제 유형: 상품 불량\n\n담당자가 확인 후 연락드리겠습니다.",
  "intent": "claim",
  "message_id": "msg_005",
  "data": {
    "ticket": {
      "ticket_id": "TICKET-1735198200",
      "order_id": "ORD-20251201-001",
      "issue_type": "defect",
      "status": "open"
    }
  }
}
```

---

# 5장: 에러 응답 및 예외 처리

## 5.1 HTTP 에러 코드

| 코드 | 의미 | 사용 상황 |
|-----|------|----------|
| 200 | OK | 정상 처리 |
| 201 | Created | 리소스 생성 성공 |
| 400 | Bad Request | 잘못된 요청 포맷 |
| 401 | Unauthorized | 인증 실패 |
| 403 | Forbidden | 권한 없음 |
| 404 | Not Found | 리소스 없음 |
| 422 | Validation Error | 데이터 검증 실패 |
| 429 | Too Many Requests | Rate Limit 초과 |
| 500 | Internal Server Error | 서버 오류 |
| 503 | Service Unavailable | 서비스 불가 |

---

## 5.2 에러 응답 포맷

### 5.2.1 일반 에러

```json
{
  "detail": "에러 메시지"
}
```

### 5.2.2 검증 에러 (422)

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    },
    {
      "loc": ["body", "password"],
      "msg": "ensure this value has at least 8 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

---

## 5.3 인증 에러 샘플

### 5.3.1 토큰 없음 (401)

```json
{
  "detail": "Not authenticated"
}
```

### 5.3.2 토큰 만료 (401)

```json
{
  "detail": "Token has expired"
}
```

### 5.3.3 유효하지 않은 토큰 (401)

```json
{
  "detail": "Could not validate credentials"
}
```

### 5.3.4 권한 없음 (403)

```json
{
  "detail": "관리자 권한이 필요합니다"
}
```

---

## 5.4 Rate Limit 에러 (429)

```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "retry_after": 60
}
```

---

## 5.5 비즈니스 로직 에러

### 5.5.1 주문 취소 불가

```json
{
  "ok": false,
  "order_id": "ORD-20251201-001",
  "status": "shipping",
  "error": "Cancellable only before shipping"
}
```

### 5.5.2 이미 존재하는 이메일

```json
{
  "detail": "이메일이 이미 존재합니다"
}
```

### 5.5.3 리소스 없음 (404)

```json
{
  "detail": "order not found"
}
```

```json
{
  "detail": "ticket not found"
}
```

---

## 5.6 가드레일 에러

### 5.6.1 입력 검증 실패

```json
{
  "detail": "메시지가 너무 깁니다. 최대 2000자까지 입력 가능합니다.",
  "code": "INPUT_TOO_LONG"
}
```

### 5.6.2 금지어 감지

```json
{
  "detail": "부적절한 표현이 포함되어 있습니다.",
  "code": "FORBIDDEN_WORD_DETECTED"
}
```

### 5.6.3 인젝션 공격 감지

```json
{
  "detail": "잠재적인 보안 위협이 감지되었습니다.",
  "code": "INJECTION_DETECTED"
}
```

---

## 5.7 서버 에러 (500)

```json
{
  "detail": "Internal server error",
  "request_id": "req_1735198200123"
}
```

---

## 5.8 서비스 불가 (503)

```json
{
  "detail": "Service temporarily unavailable",
  "retry_after": 30
}
```

---

# 부록: 빠른 참조

## A. 주요 엔드포인트 요약

| 메서드 | 엔드포인트 | 설명 |
|-------|-----------|------|
| POST | `/auth/register` | 회원가입 |
| POST | `/auth/login` | 로그인 |
| POST | `/auth/refresh` | 토큰 갱신 |
| GET | `/auth/me` | 현재 사용자 정보 |
| POST | `/conversations` | 대화 생성 |
| POST | `/conversations/{id}/messages` | 메시지 전송 ⭐ |
| GET | `/policies/search` | 정책 검색 |
| GET | `/orders/{id}` | 주문 상세 |
| POST | `/orders/{id}/cancel` | 주문 취소 |
| POST | `/tickets` | 티켓 생성 |
| GET | `/healthz` | Liveness 체크 |
| GET | `/metrics` | Prometheus 메트릭 |

## B. 의도별 payload 요약

| Intent | Sub-Intent | Payload 필드 |
|--------|-----------|--------------|
| order | list | `limit`, `status`, `include_items` |
| order | status | `order_id` |
| order | detail | `order_id` |
| order | cancel | `order_id`, `reason` |
| claim | - | `action`, `order_id`, `issue_type`, `description`, `priority` |
| policy | - | `query`, `top_k` |
| general | - | `message` |

## C. 데이터 구조 매핑

```
MessageCreate (API 입력)
       ↓
IntentResult (의도 분류)
       ↓
AgentContext (라우팅)
       ↓
AgentResponse (전문가 처리)
       ↓
final_response (API 출력)
```

---

**문서 끝**

---

> 이 문서에 대한 피드백이나 질문이 있으시면 이슈를 등록해 주세요.
