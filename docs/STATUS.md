# Project Status

## Version
v1.1.0 — STABILIZED

**최종 업데이트**: 2026-01-20

---

## 시스템 개요

한국어 기반 이커머스 고객 상담 에이전트 PoC. RDF 온톨로지 중심의 추론 엔진으로, 판단과 언어 생성을 분리한 아키텍처.

---

## 핵심 컴포넌트 구현 현황

### Agent Layer

| 컴포넌트 | 상태 | 설명 |
|---------|------|------|
| **Intent Classifier** | ✅ 완료 | 이중 분류 시스템 (LLM + 키워드 폴백) |
| **Orchestrator** | ✅ 완료 | 의도별 라우팅, 도구 실행, 응답 생성 |
| **Guardrails** | ✅ 완료 | PII 마스킹, 인젝션 방어, 정책 검증 |
| **Tracing** | ✅ 완료 | 실행 추적, 디버그 패널 |

### Data Layer

| 컴포넌트 | 상태 | 설명 |
|---------|------|------|
| **RDF Repository** | ✅ 완료 | SPARQL CRUD (Customer, Product, Order, Ticket) |
| **Fuseki Integration** | ✅ 완료 | HTTP 기반 SPARQL 엔드포인트 |
| **Vector Search** | ✅ 완료 | 임베딩 기반 유사도 검색 |
| **RAG Index** | ✅ 완료 | 정책 검색 (하이브리드: 키워드 + 벡터) |

### Ontology

| 컴포넌트 | 상태 | 설명 |
|---------|------|------|
| **OWL Schema** | ✅ 완료 | `ontology/ecommerce.ttl` |
| **SHACL Validation** | ✅ 완료 | `ontology/shacl/` |
| **Instance Data** | ✅ 완료 | 고객 100, 상품 1,492, 주문 491, 티켓 60 |
| **Embeddings** | ✅ 완료 | 1,492개 상품 벡터 (384-dim) |

### UI/API

| 컴포넌트 | 상태 | 설명 |
|---------|------|------|
| **Gradio UI** | ✅ 완료 | 8개 탭, 디버그 패널 |
| **FastAPI** | ✅ 완료 | REST + OpenAI 호환 API |
| **Authentication** | ✅ 완료 | JWT 기반 인증 |

---

## 의도 분류 시스템 현황

### 지원 의도 (Intent)

| Intent | Sub-Intent | 구현 상태 | 분류 방식 |
|--------|------------|----------|----------|
| `order` | `list` | ✅ | 키워드 + LLM |
| `order` | `detail` | ✅ | 키워드 + LLM |
| `order` | `status` | ✅ | 키워드 + LLM |
| `order` | `cancel` | ✅ | 키워드 + LLM |
| `claim` | `create` | ✅ | 키워드 + LLM |
| `policy` | - | ✅ | 키워드 + LLM |
| `recommend` | `similar` | ✅ | 키워드 + LLM |
| `recommend` | `personal` | ✅ | 키워드 + LLM |
| `recommend` | `trending` | ✅ | 키워드 + LLM |
| `recommend` | `together` | ✅ | 키워드 + LLM |
| `recommend` | `category` | ✅ | 키워드 + LLM |
| `general` | - | ✅ | 키워드 + LLM |

### 분류 성능

| 분류 방식 | 정확도 | 지연시간 | 비용 |
|----------|--------|---------|------|
| LLM (gpt-4o-mini) | ~95% | 500-1500ms | API 호출 |
| 키워드 | ~80% | <10ms | 무료 |
| 하이브리드 | ~93% | 500-1500ms | API 호출 (폴백 시 무료) |

---

## 데이터 현황

### RDF Triple Store

```
총 트리플 수: ~32,000

엔티티별:
├── Products:     1,492
├── Orders:       491
├── OrderItems:   1,240
├── Customers:    100
├── Tickets:      60
├── Similarities: 4,416
├── Embeddings:   1,492
└── SHACL Shapes: 208
```

### RAG Index

```
정책 문서: 63개
검색 모드: hybrid (키워드 30% + 벡터 70%)
임베딩 모델: intfloat/multilingual-e5-small (384-dim)
인덱스 타입: FAISS (IndexFlatIP)
```

---

## 아키텍처 Truth Order

```
Ontology (RDF Facts)
    ↓
Rule Engine (Derived Relations)
    ↓
GNN (Augmentative, Optional)
    ↓
GraphRAG (Explanation)
    ↓
UI (Observation Only)
```

---

## 제한 사항 및 알려진 이슈

### 의도적 제외

| 기능 | 이유 |
|------|------|
| Customer-Company 관계 | 현재 PoC 범위 외 |
| Company-Company 관계 | 현재 PoC 범위 외 |
| 실시간 GNN 추론 | 구현 복잡도, 향후 버전 고려 |

### 알려진 이슈

| 이슈 | 상태 | 설명 |
|------|------|------|
| Gradio 6.0 CSS 경고 | 📝 문서화 | CSS 파라미터 위치 변경 권고 (기능 영향 없음) |
| LSP 타입 경고 | 📝 인지 | FusekiStore 타입 호환 경고 (런타임 영향 없음) |

---

## 다음 버전 계획

### v1.2 (예정)

- [ ] GNN 실시간 추론 통합
- [ ] 다국어 지원 (영어, 일본어)
- [ ] 성능 최적화 (캐싱, 배치 처리)
- [ ] 모니터링 대시보드 강화

### v2.0 (장기)

- [ ] 멀티 테넌트 지원
- [ ] 도메인 팩 시스템
- [ ] A/B 테스팅 프레임워크
- [ ] 온라인 러닝 지원
