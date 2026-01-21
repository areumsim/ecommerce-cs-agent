# Glossary

이 문서는 시스템에서 사용되는 핵심 용어와 데이터 구조를 정의한다.

---

## 핵심 개념

### Ontology
: 시스템이 사실로 인정하는 개념과 구조의 집합. RDF/OWL 형식으로 정의되며, `ontology/ecommerce.ttl`에 스키마가 있다.

### Rule
: 사실을 판단으로 변환하는 명시적 논리. 동일 입력에 항상 동일 결과를 생성하는 결정론적 규칙.

### Derived Relation
: 규칙 실행 결과로 생성된 판단. 원본 사실(Fact)과 구분되며, 추론 경로 추적이 가능하다.

### Truth Order
: 진실이 생성되고 전달되는 논리적 순서: `Ontology → Rules → GNN → Explanation → UI`

### External Knowledge
: 출처와 신뢰도를 가진 비권위적 정보. 판단의 참고 자료일 뿐, 기준이 아니다.

### Augmentative
: 판단을 보조하지만 결정을 내리지 않는 역할. GNN이 이 역할을 수행한다.

---

## Agent Layer 용어

### Intent
: 사용자 입력의 주 의도. `order`, `claim`, `policy`, `recommend`, `general` 중 하나.

### Sub-Intent
: 의도의 세부 분류. 예: `order/list`, `order/detail`, `order/cancel`.

### IntentResult
: 의도 분류 결과를 담는 데이터 구조.

```python
@dataclass
class IntentResult:
    intent: str           # 주 의도
    sub_intent: str       # 세부 의도
    payload: Dict         # 추출된 파라미터
    confidence: str       # 신뢰도: low, medium, high
    source: str           # 분류 출처: "keyword" 또는 "llm"
    reason: str           # 분류 근거
```

### AgentState
: 오케스트레이터가 관리하는 상태 객체.

```python
@dataclass
class AgentState:
    user_id: str
    intent: str
    sub_intent: Optional[str]
    payload: Dict[str, Any]
    final_response: Optional[Dict] = None
```

### Orchestrator
: 의도별 라우팅, 도구 실행, 응답 생성을 담당하는 중앙 제어 컴포넌트.

---

## Data Layer 용어

### RDF (Resource Description Framework)
: 그래프 기반 데이터 모델. 주어-술어-목적어(Subject-Predicate-Object) 트리플로 사실을 표현.

### SPARQL
: RDF 데이터를 질의하는 표준 쿼리 언어.

### Fuseki
: Apache Jena 프로젝트의 SPARQL 서버. HTTP 기반 엔드포인트 제공.

### Triple
: RDF의 기본 단위. `<주어> <술어> <목적어>` 형식.

### SHACL (Shapes Constraint Language)
: RDF 데이터의 유효성을 검증하는 제약 언어.

---

## RAG 용어

### RAG (Retrieval-Augmented Generation)
: 검색 결과를 컨텍스트로 활용하여 응답을 생성하는 방식.

### PolicyHit
: 정책 검색 결과를 담는 데이터 구조.

```python
@dataclass
class PolicyHit:
    id: str               # 문서 ID
    score: float          # 검색 점수 (0-1)
    text: str             # 정책 본문
    metadata: Dict        # 메타데이터 (title, doc_type, ...)
```

### Hybrid Search
: 키워드 검색과 벡터 검색을 결합한 검색 방식. 기본 가중치: 키워드 30% + 벡터 70%.

### Embedding
: 텍스트를 고정 차원의 벡터로 변환한 표현. 384차원 (multilingual-e5-small).

### FAISS
: Facebook AI Similarity Search. 대규모 벡터 유사도 검색 라이브러리.

---

## Guardrails 용어

### PII (Personally Identifiable Information)
: 개인 식별 정보. 전화번호, 이메일, 주민번호, 카드번호 등.

### Prompt Injection
: 악의적 지시를 입력에 삽입하여 시스템 동작을 조작하려는 공격.

### InputGuardResult
: 입력 가드레일 처리 결과.

```python
@dataclass
class InputGuardResult:
    blocked: bool              # 차단 여부
    block_reason: Optional[str]  # 차단 사유
    sanitized_text: str        # 정제된 텍스트
    pii_detected: List[Dict]   # 감지된 PII 목록
    warnings: List[str]        # 경고 메시지
```

### OutputGuardResult
: 출력 가드레일 처리 결과.

```python
@dataclass
class OutputGuardResult:
    sanitized_text: str        # 정제된 응답
    pii_masked: List[Dict]     # 마스킹된 PII
    policy_violations: List[Dict]  # 정책 위반 목록
    warnings: List[str]        # 경고
```

---

## RDF Entity 용어

### Customer
: 고객 엔티티. `customerId`, `name`, `email`, `membershipLevel` 속성.

### Product
: 상품 엔티티. `productId`, `title`, `brand`, `price`, `averageRating` 속성.

### Order
: 주문 엔티티. `orderId`, `status`, `orderDate`, `totalAmount` 속성.

### OrderItem
: 주문 항목 엔티티. `quantity`, `unitPrice`, `hasProduct`, `belongsToOrder` 속성.

### Ticket
: 지원 티켓 엔티티. `ticketId`, `issueType`, `priority`, `status` 속성.

---

## 설정 용어

### llm_classification.enabled
: LLM 기반 의도 분류 활성화 여부 (`configs/intents.yaml`).

### llm_classification.fallback_to_keyword
: LLM 분류 실패 시 키워드 분류로 폴백할지 여부.

### llm_classification.confidence_threshold
: LLM 분류 결과의 최소 신뢰도. `low`, `medium`, `high` 중 하나.

### retrieval.mode
: RAG 검색 모드. `keyword`, `embedding`, `hybrid` 중 하나.

### retrieval.hybrid_alpha
: 하이브리드 검색에서 벡터 검색 가중치 (0=키워드만, 1=벡터만).

---

## 추적/모니터링 용어

### Trace
: 실행 과정의 개별 기록. 유형, 입력, 출력, 소요 시간 포함.

### add_trace()
: 추적 기록을 추가하는 함수.

```python
add_trace(
    type="tool",              # 추적 유형
    description="주문 조회",   # 설명
    input_data={...},         # 입력
    output_data={...},        # 출력
    duration_ms=123.45,       # 소요 시간 (밀리초)
    success=True              # 성공 여부
)
```

### Debug Panel
: UI에서 실행 추적을 실시간으로 보여주는 패널.
