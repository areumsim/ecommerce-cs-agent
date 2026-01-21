# Technology Overview

## Ontology‑Centric Reasoning Engine

이 문서는 이 프로젝트의 **기술 백서(Technical Whitepaper)** 역할을 한다. 단순한 개념 요약이나 가이드가 아니라, 이 시스템이 왜 이런 구조를 가지는지, 각 구성 요소가 어떤 책임을 가지며 어떻게 상호작용하는지를 **실제 시스템 수준에서 상세하게 설명**한다.

---

## 1. 문제 정의: 왜 이런 시스템이 필요한가

최근 많은 AI 시스템은 대규모 언어 모델(LLM)을 중심으로 설계된다. 이러한 접근은 빠른 구현과 자연스러운 인터페이스를 제공하지만, 다음과 같은 구조적 한계를 가진다.

- 결과가 확률적이며 재현이 어렵다
- 동일한 입력에 대해 서로 다른 판단이 발생할 수 있다
- 왜 그런 결론이 나왔는지 명확하게 설명하기 어렵다
- 규제, 감사, 책임 분리가 필요한 환경에 적합하지 않다

이 프로젝트는 이러한 문제를 해결하기 위해 **판단과 언어를 분리**하는 방향으로 설계되었다.

> 판단은 구조화된 지식과 규칙이 담당하고, 언어 모델은 그 결과를 설명만 한다.

---

## 2. 시스템의 핵심 원칙

### 2.1 Ontology First

이 시스템에서 Ontology는 단순한 스키마나 데이터 모델이 아니다. Ontology는 다음을 정의한다.

- 시스템이 어떤 개념을 세계의 구성 요소로 인정하는가
- 어떤 관계가 의미적으로 허용되는가
- 어떤 데이터만이 "사실(Truth)"로 취급되는가

Customer, Order, Product와 같은 엔티티는 단순한 테이블 레코드가 아니라, **의미를 가진 개념 객체**이다. Ontology에 포함된 데이터만이 이 시스템에서 사실로 인정된다.

---

### 2.2 Rule‑based Reasoning

이 시스템의 모든 판단은 **명시적인 규칙(Rule)** 에 의해 이루어진다.

- 규칙은 사람이 읽고 이해할 수 있어야 한다
- 규칙은 동일한 입력에 대해 항상 동일한 결과를 생성해야 한다
- 규칙은 테스트 및 검증이 가능해야 한다

예를 들어, 고객이 특정 상품군을 반복 구매했다면 이는 단순한 로그가 아니라, 규칙에 의해 **선호(Preference)** 라는 판단으로 변환된다.

---

### 2.3 LLM의 역할 제한

LLM은 이 시스템에서 의도적으로 제한된 역할만 수행한다.

#### LLM이 수행하는 작업 (허용 영역)

| 역할 | 설명 | 실패 시 폴백 |
|------|------|-------------|
| **의도 분류** | 사용자 입력을 intent/sub_intent로 분류 | 키워드 기반 분류로 폴백 |
| **응답 생성** | 도구 결과를 자연어로 변환 | 템플릿 응답으로 폴백 |
| **설명 생성** | 추론 그래프를 자연어로 설명 | 구조화된 JSON 반환 |

#### LLM이 수행하지 않는 작업 (금지 영역)

| 금지 역할 | 이유 |
|----------|------|
| **판단 생성** | 결정론적 규칙만 판단 가능 |
| **규칙 대체** | 규칙은 명시적, 검증 가능해야 함 |
| **온톨로지 수정** | 사실은 RDF/TTL로만 관리 |
| **데이터 생성** | 도구 결과만 응답에 포함 |
| **정책 결정** | 정책은 RAG 검색으로만 참조 |

#### LLM 실패 시 시스템 동작

이 시스템은 **LLM 없이도 완전히 동작**하도록 설계되었다:

```
의도 분류: LLM 실패 → 키워드 기반 분류 (classify_intent_keyword)
응답 생성: LLM 실패 → 템플릿 응답 (_format_template_response)
```

#### LLM 사용 지점 (코드 레벨)

| 함수 | 파일 | 역할 | 폴백 |
|------|------|------|------|
| `classify_intent_llm()` | `intent_classifier.py` | 의도 분류 | `classify_intent_keyword()` |
| `generate_response()` | `llm/client.py` | 응답 생성 | `_format_template_response()` |
| `generate_routed_response()` | `llm/router.py` | 라우팅된 응답 | `generate_response()` |

이 경계는 시스템의 **신뢰성**, **설명 가능성**, **재현 가능성**을 유지하기 위해 강제된다.

---

## 3. End‑to‑End 실행 흐름

시스템의 전체 실행 흐름은 다음과 같이 고정되어 있다.

```
User Input
 → Guardrails
 → Intent Classification
 → Orchestrator
 → Ontology Query
 → Rule Engine
 → Derived Relations
 → (Optional) GNN Augmentation
 → Explanation (GraphRAG)
 → UI
```

어떤 구성 요소도 이 순서를 우회하거나 생략할 수 없다.

---

## 4. Guardrails: 입력 안정화 계층

Guardrails는 시스템에 들어오는 입력을 **의미 해석 이전 단계**에서 처리한다.

- 개인정보(PII) 제거
- Prompt Injection 패턴 차단
- 비정상 입력 정규화

이 단계에서는 LLM을 사용하지 않는다. Guardrails의 목적은 지능이 아니라 **안정성**이다.

---

## 5. Intent Classification: 경로 결정 계층

Intent Classification은 사용자 입력이 어떤 기능 경로로 연결될지를 결정한다.

### 5.1 이중 분류 시스템 (Dual Classification)

이 시스템은 **LLM-First with Keyword Fallback** 전략을 사용한다:

```
1. LLM 분류 시도 (활성화된 경우)
   ├── 성공 + 신뢰도 충족 → IntentResult 반환
   └── 실패 또는 저신뢰 → 다음 단계
2. 키워드 분류 (폴백)
   └── 항상 결과 반환 (unknown 포함)
```

### 5.2 키워드 분류의 역할

키워드 분류는 **규칙 기반 패턴 매칭**으로 동작:

- **주문 ID 패턴**: `ORD-xxx` 또는 `ORD_xxx` 형식 탐지
- **의도 키워드**: 각 의도별 키워드 목록 (`configs/intents.yaml`)
- **우선순위**: 주문 ID > 정책 > 주문 > 클레임 > 추천 > 일반

### 5.3 LLM 분류의 역할

LLM 분류는 **자연어 이해 기반 분류**로 동작:

- JSON 형식 응답 파싱
- 신뢰도(confidence) 평가
- 엔티티 추출 (order_id, issue_type, query)

### 5.4 분류 결과 구조

```python
IntentResult(
    intent="order",           # 주 의도
    sub_intent="status",      # 세부 의도
    payload={"order_id": "ORD-001"},  # 추출된 파라미터
    confidence="high",        # 신뢰도
    source="keyword",         # 분류 출처: "keyword" 또는 "llm"
    reason="주문 ID + 상태 키워드 탐지"  # 분류 근거
)
```

### 5.5 안전성 보장

Intent 분류가 잘못되더라도 이후 단계의 판단은 **Ontology와 Rule에 의해 수행**되므로, 시스템의 진실성은 훼손되지 않는다. 이는 다음을 의미한다:

- 잘못된 의도 → 잘못된 도구 호출 → **빈 결과 또는 에러** (거짓 정보 생성 없음)
- 올바른 의도 → 올바른 도구 호출 → **RDF 사실 기반 결과**

---

## 6. Orchestrator: 제어 계층

Orchestrator는 시스템의 제어 흐름만을 담당한다.

- 실행 경로 분기
- Tool 호출

비즈니스 판단이나 데이터 수정은 수행하지 않는다.

---

## 7. Ontology Truth Layer

Ontology Truth Layer는 시스템에서 "사실"의 기준이 되는 계층이다.

- RDF/OWL 기반
- 내부 시스템 데이터만 포함
- 외부 정보 제외

이 계층에 존재하는 데이터만이 판단의 입력으로 사용된다.

---

## 8. Rule Engine

Rule Engine은 이 시스템의 판단 핵심이다.

- Ontology fact를 입력으로 사용
- 조건 충족 시 Derived Relation 생성
- 결정론적 동작

규칙은 코드가 아니라 **논리적 선언**에 가깝다.

---

## 9. External Knowledge Layer

현실 세계의 정보는 불확실하다. 따라서 외부 정보는 Truth Layer와 분리된다.

External Knowledge는 다음 정보를 반드시 포함한다.
- 출처(Source)
- 신뢰도(Confidence)
- 관측 시점(Time)

External Knowledge는 판단의 참고 자료일 뿐, 기준이 아니다.

---

## 10. GNN Augmentation

GNN은 데이터 희소성을 보완하기 위한 **보조 계층**이다.

- 후보 확장
- 순위 보정

Rule 결과를 덮어쓰지 않으며, 단독 판단을 수행하지 않는다.

---

## 11. Explanation Layer (GraphRAG)

Explanation Layer는 추론 과정을 그래프로 구성한 뒤, 이를 자연어로 설명한다.

- 입력: 확정된 reasoning graph
- 출력: 설명 텍스트

LLM은 이 단계에서만 사용되며, 새로운 사실을 생성하지 않는다.

---

## 12. UI Layer

UI는 시스템의 판단을 **관찰하는 인터페이스**이다.

- Inspection only
- 데이터 수정 불가
- 판단 실행 불가

UI가 판단을 가지지 않도록 설계되어 있다.

---

## 13. Truth Order (불변 규칙)

```
Ontology
 → Rule Engine
 → External Knowledge (참고)
 → GNN (보조)
 → Explanation
 → UI
```

이 순서는 시스템 설계의 헌법이며 변경되지 않는다.

---

## 14. 범위 선언

이 문서는 개념과 구조를 설명한다. 현재 구현 범위는 STATUS.md를 참조한다.
