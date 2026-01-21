# First Day Guide

## 시스템 탐색 매뉴얼

이 문서는 이 시스템을 처음 접하는 개발자가 **구조와 판단 흐름을 이해**하기 위한 실습 가이드이다.

---

## 1. 올바른 관점

이 시스템은 **답을 생성하는 AI가 아니다**. 

이 시스템은:
- 사실(Fact)을 저장하고
- 규칙(Rule)으로 판단하고
- 결과를 설명하는 시스템이다

LLM은 **설명자** 역할만 한다. LLM 없이도 시스템은 완전히 동작한다.

---

## 2. 첫 번째 실습: UI 둘러보기

### 2.1 UI 실행

```bash
cd ecommerce-cs-agent
python ui.py
# → http://localhost:7860 접속
```

### 2.2 탭 구조 이해

| 탭 | 목적 | 첫날 중요도 |
|----|------|-----------|
| **상담** | 채팅 인터페이스 | 높음 |
| **대시보드** | 데이터 통계 | 중간 |
| **지식그래프** | 온톨로지 시각화 | 높음 |
| **개발자 도구** | SPARQL, NL→SPARQL | 중간 |

### 2.3 상담 탭에서 해볼 것

1. 고객 선택 → `user_001` 선택
2. 메시지 입력:
   - `내 주문 보여줘`
   - `ORD-20251201-001 상태 알려줘`
   - `환불 정책 알려줘`
3. **디버그 패널** 확인:
   - 의도 분류 결과 (키워드 vs LLM)
   - 도구 호출 내역
   - 실행 시간

---

## 3. 두 번째 실습: 의도 분류 이해하기

### 3.1 키워드 분류 관찰

다음 메시지를 입력하고 디버그 패널의 `source` 필드를 확인:

| 메시지 | 예상 결과 |
|--------|----------|
| `내 주문 보여줘` | `source: keyword`, `intent: order` |
| `환불 정책이 뭐야` | `source: keyword`, `intent: policy` |
| `추천해줘` | `source: keyword`, `intent: recommend` |

### 3.2 주문 ID 패턴 관찰

주문 ID가 포함되면 **자동으로 추출**된다:

| 메시지 | 추출 결과 |
|--------|----------|
| `ORD-001 취소해줘` | `order_id: ORD-001`, `sub_intent: cancel` |
| `ORD_20251201_001 상태` | `order_id: ORD_20251201_001`, `sub_intent: status` |

### 3.3 LLM 분류 관찰

LLM 분류가 사용되면 `source: llm`으로 표시된다. 다음을 확인:

- `confidence`: high/medium/low
- `reason`: LLM이 판단한 근거

---

## 4. 세 번째 실습: 지식그래프 탐색

### 4.1 지식그래프 탭 접속

1. 지식그래프 탭 클릭
2. 고객 선택 → 그래프 렌더링 확인

### 4.2 선과 점선의 의미

| 표시 | 의미 | 예시 |
|------|------|------|
| **실선** | Ontology Fact (사실) | Customer → Order |
| **점선** | Derived Relation (판단) | Customer → PreferredCategory |
| **[External]** | 외부 참고 정보 | Company 데이터 |

### 4.3 SPARQL 쿼리 실행

개발자 도구 탭에서 직접 쿼리 실행:

```sparql
# 고객의 주문 목록
SELECT ?orderId ?status ?totalAmount
WHERE {
    ?order a ecom:Order ;
           ecom:orderedBy ?customer ;
           ecom:orderId ?orderId ;
           ecom:status ?status ;
           ecom:totalAmount ?totalAmount .
    ?customer ecom:customerId "user_001" .
}
LIMIT 10
```

---

## 5. 네 번째 실습: 코드 구조 파악

### 5.1 핵심 파일 위치

```
src/agents/
├── nodes/intent_classifier.py  ← 의도 분류 (이것부터!)
├── orchestrator.py             ← 실행 흐름
└── tools/order_tools.py        ← 도구 함수

src/rdf/
├── store.py                    ← Fuseki 연결
└── repository.py               ← SPARQL CRUD

configs/
├── intents.yaml                ← 의도 키워드 설정
└── guardrails.yaml             ← 가드레일 패턴
```

### 5.2 의도 분류기 읽기

`src/agents/nodes/intent_classifier.py`를 열고:

1. `classify_intent_keyword()` 함수 찾기 (54행~)
2. 키워드 매칭 로직 이해
3. `classify_intent_llm()` 함수 찾기 (324행~)
4. LLM 응답 파싱 로직 이해

### 5.3 오케스트레이터 읽기

`src/agents/orchestrator.py`를 열고:

1. `run()` 함수 찾기 (245행~)
2. 의도별 분기 확인 (`if state.intent == "order":`)
3. `add_trace()` 호출 위치 확인

---

## 6. 첫날에 수정하면 안 되는 것

| 영역 | 이유 |
|------|------|
| **ontology/*.ttl** | 스키마 변경은 전체 데이터에 영향 |
| **configs/intents.yaml** | 의도 분류 동작 변경 |
| **src/guardrails/** | 보안 로직 손상 위험 |

---

## 7. 첫날 목표 체크리스트

- [ ] UI 8개 탭 둘러보기
- [ ] 채팅으로 3가지 의도 테스트 (order, policy, recommend)
- [ ] 디버그 패널에서 의도 분류 결과 확인
- [ ] 지식그래프 시각화 확인
- [ ] SPARQL 쿼리 1개 직접 실행
- [ ] `intent_classifier.py` 코드 읽기
- [ ] `orchestrator.py` 흐름 파악

---

## 8. 다음 단계

첫날 목표를 완료했다면:

1. **ARCHITECTURE.md** 읽기 - 전체 아키텍처 이해
2. **GLOSSARY.md** 참조 - 용어 정의 확인
3. **STATUS.md** 확인 - 구현 현황 파악
4. 테스트 실행: `pytest tests/ -q`

---

## 9. 도움이 필요할 때

### 문서

| 문서 | 내용 |
|------|------|
| `ARCHITECTURE.md` | 전체 아키텍처 |
| `TECHNOLOGY_OVERVIEW.md` | 기술 철학 |
| `GLOSSARY.md` | 용어 정의 |
| `STATUS.md` | 구현 현황 |
| `src/*/AGENTS.md` | 모듈별 가이드 |

### 코드 주석

모든 주요 함수에 docstring이 있다:

```python
async def classify_intent_async(message: str) -> IntentResult:
    """비동기 의도 분류 (LLM 우선, 키워드 폴백).
    
    Args:
        message: 사용자 입력 메시지
        
    Returns:
        IntentResult: 분류 결과
    """
```
