# API Reference

Ecommerce Agent API v0.2.0 문서

## 기본 정보

- **Base URL**: `http://localhost:8000`
- **인증**: Bearer Token (JWT)
- **Content-Type**: `application/json`

## 인증

### 회원가입

```http
POST /auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "홍길동"
}
```

**Response (201 Created):**
```json
{
  "id": "user_abc123",
  "email": "user@example.com",
  "name": "홍길동",
  "role": "user",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 로그인

```http
POST /auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 토큰 갱신

```http
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
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 현재 사용자 정보

```http
GET /auth/me
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "id": "user_abc123",
  "email": "user@example.com",
  "name": "홍길동",
  "role": "user",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 로그아웃

```http
POST /auth/logout
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "message": "로그아웃 완료 (1개 토큰 무효화)"
}
```

---

## 대화 (Conversations)

### 새 대화 시작

```http
POST /conversations
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "title": "주문 문의",
  "metadata": {"source": "web"}
}
```

**Response (201 Created):**
```json
{
  "id": "conv_abc123",
  "user_id": "user_abc123",
  "title": "주문 문의",
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "message_count": 0
}
```

### 대화 목록 조회

```http
GET /conversations?status=active&limit=20
Authorization: Bearer {access_token}
```

**Query Parameters:**
| 파라미터 | 타입 | 설명 | 기본값 |
|---------|------|------|--------|
| status | string | 상태 필터 (active, closed) | - |
| limit | int | 조회 개수 (1-100) | 20 |

**Response (200 OK):**
```json
[
  {
    "id": "conv_abc123",
    "user_id": "user_abc123",
    "title": "주문 문의",
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "message_count": 5
  }
]
```

### 대화 상세 조회

```http
GET /conversations/{conversation_id}
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "id": "conv_abc123",
  "user_id": "user_abc123",
  "title": "주문 문의",
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "messages": [
    {
      "id": "msg_abc123",
      "role": "user",
      "content": "주문 상태를 확인하고 싶어요",
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": "msg_abc124",
      "role": "assistant",
      "content": "주문번호를 알려주시면 확인해드리겠습니다.",
      "created_at": "2024-01-01T00:00:01Z"
    }
  ]
}
```

### 메시지 전송

```http
POST /conversations/{conversation_id}/messages
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "content": "ORD-20240101-001 주문 상태를 확인해주세요"
}
```

**Response (200 OK):**
```json
{
  "conversation_id": "conv_abc123",
  "success": true,
  "message": "주문 상태 조회 결과입니다...",
  "data": {
    "order_status": "배송중",
    "tracking_number": "1234567890"
  }
}
```

### 대화 종료

```http
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

## 정책 검색 (Policies)

### 정책 검색

```http
GET /policies/search?q={query}&top_k=5
```

**Query Parameters:**
| 파라미터 | 타입 | 설명 | 기본값 |
|---------|------|------|--------|
| q | string | 검색 쿼리 (필수) | - |
| top_k | int | 결과 개수 | 5 |

**Response (200 OK):**
```json
{
  "query": "환불 정책",
  "hits": [
    {
      "id": "policy_001",
      "score": 0.95,
      "text": "환불은 결제일로부터 7일 이내에 가능합니다...",
      "metadata": {
        "category": "환불",
        "updated_at": "2024-01-01"
      }
    }
  ]
}
```

---

## 주문 (Orders)

### 사용자 주문 목록

```http
GET /users/{user_id}/orders?status=delivered&limit=10
```

**Query Parameters:**
| 파라미터 | 타입 | 설명 | 기본값 |
|---------|------|------|--------|
| status | string | 주문 상태 필터 | - |
| limit | int | 조회 개수 | 10 |

**Response (200 OK):**
```json
{
  "orders": [
    {
      "order_id": "ORD-20240101-001",
      "user_id": "user_abc123",
      "status": "delivered",
      "total_amount": 50000,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 주문 상세

```http
GET /orders/{order_id}
```

**Response (200 OK):**
```json
{
  "order": {
    "order_id": "ORD-20240101-001",
    "user_id": "user_abc123",
    "status": "delivered",
    "total_amount": 50000,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "items": [
    {
      "product_id": "prod_001",
      "name": "상품명",
      "quantity": 2,
      "price": 25000
    }
  ]
}
```

### 주문 상태

```http
GET /orders/{order_id}/status
```

**Response (200 OK):**
```json
{
  "status": {
    "order_id": "ORD-20240101-001",
    "status": "delivered",
    "tracking_number": "1234567890",
    "carrier": "택배사",
    "updated_at": "2024-01-01T12:00:00Z"
  }
}
```

### 주문 취소

```http
POST /orders/{order_id}/cancel
```

**Request Body:**
```json
{
  "reason": "단순 변심"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "주문 취소 요청이 접수되었습니다",
  "cancel_request_id": "cancel_abc123"
}
```

---

## 티켓 (Tickets)

### 티켓 생성

```http
POST /tickets
```

**Request Body:**
```json
{
  "user_id": "user_abc123",
  "order_id": "ORD-20240101-001",
  "issue_type": "refund",
  "description": "상품 불량으로 환불 요청합니다",
  "priority": "high"
}
```

**Response (200 OK):**
```json
{
  "ticket": {
    "ticket_id": "TKT-20240101-001",
    "user_id": "user_abc123",
    "order_id": "ORD-20240101-001",
    "issue_type": "refund",
    "status": "open",
    "priority": "high",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### 티켓 조회

```http
GET /tickets/{ticket_id}
```

**Response (200 OK):**
```json
{
  "ticket": {
    "ticket_id": "TKT-20240101-001",
    "user_id": "user_abc123",
    "order_id": "ORD-20240101-001",
    "issue_type": "refund",
    "description": "상품 불량으로 환불 요청합니다",
    "status": "open",
    "priority": "high",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### 사용자 티켓 목록

```http
GET /users/{user_id}/tickets?status=open&limit=20
```

**Query Parameters:**
| 파라미터 | 타입 | 설명 | 기본값 |
|---------|------|------|--------|
| status | string | 티켓 상태 필터 | - |
| limit | int | 조회 개수 | 20 |

**Response (200 OK):**
```json
{
  "tickets": [
    {
      "ticket_id": "TKT-20240101-001",
      "issue_type": "refund",
      "status": "open",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 티켓 해결

```http
POST /tickets/{ticket_id}/resolve
```

**Response (200 OK):**
```json
{
  "ticket": {
    "ticket_id": "TKT-20240101-001",
    "status": "resolved",
    "resolved_at": "2024-01-01T12:00:00Z"
  }
}
```

---

## 이미지 분석 (Vision)

### 이미지 분석

```http
POST /vision/analyze
```

**Request Body:**
```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "analysis_type": "product"
}
```

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| image_base64 | string | Base64 인코딩된 이미지 |
| analysis_type | string | 분석 유형 (product, defect) |

**Response (200 OK):**
```json
{
  "success": true,
  "analysis_type": "product",
  "description": "흰색 티셔츠입니다",
  "confidence": 0.95,
  "labels": ["의류", "티셔츠", "흰색"],
  "attributes": {
    "color": "white",
    "category": "clothing"
  }
}
```

### 불량 탐지

```http
POST /vision/defect
```

**Request Body:**
```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "analysis_type": "defect",
  "description": "이미지에서 불량이 감지되지 않았습니다",
  "confidence": 0.98,
  "labels": ["정상"],
  "attributes": {
    "defect_detected": false
  }
}
```

---

## 채팅 (Chat)

### 단일 메시지 채팅

```http
POST /chat
```

**Request Body:**
```json
{
  "user_id": "user_abc123",
  "message": "내 주문 상태를 확인해줘"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "주문번호를 알려주시면 상태를 확인해드리겠습니다.",
  "intent": "order",
  "sub_intent": "status"
}
```

### 스트리밍 채팅 (SSE)

Server-Sent Events (SSE) 형식으로 실시간 스트리밍 응답을 받습니다.

```http
POST /chat/stream
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "환불 정책을 설명해줘",
  "system_prompt": "친절한 상담원으로 답변해주세요"  // optional
}
```

**Response (200 OK, text/event-stream):**
```
data: 환불

data: 정책에

data: 대해

data: 안내

data: 드리겠습니다.

data: [DONE]
```

#### curl 예제

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "배송 정책 알려줘"}'
```

#### Python 예제

```python
import httpx

async def stream_chat():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/chat/stream",
            json={"message": "환불 정책 알려줘"},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    content = line[6:]
                    if content == "[DONE]":
                        break
                    print(content, end="", flush=True)
```

#### JavaScript 예제

```javascript
const response = await fetch("http://localhost:8000/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "배송 정책 알려줘" }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  const lines = text.split("\n");

  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const content = line.slice(6);
      if (content === "[DONE]") break;
      console.log(content);
    }
  }
}
```

#### 응답 형식

| 데이터 | 설명 |
|--------|------|
| `data: {text}` | 응답 텍스트 청크 |
| `data: [DONE]` | 스트리밍 완료 신호 |

#### 에러 응답

스트리밍 중 오류 발생 시:
```
data: [ERROR] 오류 메시지

data: [DONE]
```

---

## 모니터링

### 헬스체크 (간단)

```http
GET /healthz
```

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

### 헬스체크 (상세)

```http
GET /health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "components": {
    "database": {"status": "up"},
    "rag_index": {"status": "up", "documents": 150}
  }
}
```

### 준비 상태

```http
GET /ready
```

**Response (200 OK):**
```json
{
  "status": "ready"
}
```

### Prometheus 메트릭

```http
GET /metrics
```

**Response (200 OK):**
```text
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/healthz",status="200"} 100
...
```

---

## 에러 응답

모든 에러는 다음 형식으로 반환됩니다:

```json
{
  "error": "ERROR_CODE",
  "message": "사람이 읽을 수 있는 에러 메시지",
  "details": {}
}
```

### 에러 코드

| 코드 | HTTP 상태 | 설명 |
|-----|----------|------|
| AUTH_ERROR | 401 | 인증 실패 |
| PERMISSION_DENIED | 403 | 권한 부족 |
| NOT_FOUND | 404 | 리소스 없음 |
| VALIDATION_ERROR | 400 | 입력 검증 실패 |
| RATE_LIMIT_EXCEEDED | 429 | 요청 제한 초과 |
| INTERNAL_ERROR | 500 | 내부 서버 오류 |
