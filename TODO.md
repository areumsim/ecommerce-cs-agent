# TODO - 이커머스 CS 에이전트

**마지막 업데이트**: 2026-01-19

---

## 현재 상태 요약

| 영역 | UI (Gradio) | API (FastAPI) | 비고 |
|------|:-----------:|:-------------:|------|
| 데이터 저장소 | ✅ Fuseki | ✅ Fuseki | 통합 완료 |
| 추천 시스템 | ✅ SPARQL | ✅ SPARQL | 통합 완료 |
| 벡터 검색 | ✅ RDF 임베딩 | ❌ 미구현 | API 엔드포인트 필요 |

**Fuseki 현황**: ~32,000 트리플 (Products 1,492 / Orders 491 / Customers 100 / Tickets 60)

---

## 🟡 우선순위 중간

### 1. 벡터 검색 API 엔드포인트
**상태**: 미구현  
**설명**: UI에서는 벡터 검색 가능하지만 API에는 엔드포인트 없음

**해야 할 일:**
- [ ] `GET /search/semantic?q=...` 엔드포인트 추가
- [ ] 제품 임베딩 기반 유사도 검색 제공

### 2. 통합 테스트 보강
**상태**: 부분 완료  
**설명**: RDF 모듈 테스트는 있지만 E2E 통합 테스트 부족

**해야 할 일:**
- [ ] UI + Fuseki 통합 테스트
- [ ] API + Fuseki 통합 테스트

### 3. 레거시 코드 정리
**상태**: deprecation 표시 완료  
**설명**: `src/mock_system/`, `src/graph/` 모듈은 deprecated 표시됨

**해야 할 일:**
- [ ] 의존하는 specialists 코드 제거 또는 RDF로 마이그레이션
- [ ] `src/agents/router.py` → `src/agents/orchestrator.py`로 통합 검토

---

## 🟢 우선순위 낮음 (개선사항)

### 4. 임베딩 자동 갱신
- [ ] 새 상품 추가 시 임베딩 자동 생성
- [ ] 배치 vs 실시간 전략 결정

### 5. SHACL 검증 자동화
- [ ] 데이터 로드 시 SHACL 검증 실행
- [ ] 검증 실패 시 알림

### 6. OWL 추론 활용
- [ ] Fuseki에서 OWL 추론 활성화 검토
- [ ] inverse property 자동 추론 활용

---

## ✅ 완료된 항목

### 지식그래프 UI 개선 (2026-01-19)
- [x] 그래프 노드 폰트 색상 수정 - 어두운 글씨(`#1e1e2e`)로 가독성 향상
- [x] 온톨로지 스키마에 카테고리 노드 추가 (Category, Electronics, MobilePhone 등)
- [x] 카테고리 계층 구조 엣지 추가 (subClassOf 관계)
- [x] 상품 유사도 그래프 개선 - "N/A" 제거, 엣지 두께 추가
- [x] RDF 데이터 관리 탭 추가 (SPARQL 쿼리, 트리플 관리, 엔티티 브라우저)
- [x] `scripts/export_visualization_data.py` - 카테고리 그룹/색상 분리

### Fuseki 마이그레이션 (2026-01-16)
- [x] UI + API 모두 Fuseki 단일 백엔드로 통합
- [x] `src/rdf/repository.py` - Order/Ticket CRUD 추가
- [x] `src/agents/tools/order_tools.py` - RDF 기반으로 전환
- [x] `src/recommendation/service.py` - RDF 기반으로 전환
- [x] `api.py` health check - Fuseki triple count 반환

### 문서 업데이트 (2026-01-16)
- [x] `AGENTS.md` - Fuseki 아키텍처 반영
- [x] `README.md` - Fuseki 기반으로 재작성
- [x] `docs/ARCHITECTURE.md` - Fuseki 기반으로 전면 재작성 (architecture.md 통합)
- [x] `docs/operations.md` - Fuseki 스토리지 섹션
- [x] `docs/rdf_integration.md` - Fuseki 통합 가이드

### OWL 온톨로지 확장 (2026-01-16)
- [x] Inverse properties (purchased ↔ purchasedBy, etc.)
- [x] Functional properties (customerId, orderId, etc.)
- [x] Disjoint classes
- [x] Cardinality restrictions

### 레거시 코드 deprecation (2026-01-16)
- [x] `src/graph/__init__.py` - deprecation warning
- [x] `src/mock_system/__init__.py` - deprecation warning

### RDF 통합 (이전)
- [x] `src/rdf/store.py` - FusekiStore 구현
- [x] `src/rdf/repository.py` - RDFRepository 구현
- [x] `ontology/` - 온톨로지 및 인스턴스 데이터
- [x] `ontology/shacl/` - SHACL 검증 규칙
- [x] `scripts/12_generate_mock_ttl.py` - CSV → TTL (tickets 포함)
- [x] `scripts/15_generate_embeddings.py` - 임베딩 생성
- [x] `tests/test_rdf.py` - RDF 테스트

---

## 명령어 참조

```bash
# Fuseki 상태 확인
curl -s http://ar_fuseki:3030/$/ping

# 트리플 수 확인
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'

# RDF Repository 테스트
python -c "
from src.rdf.repository import get_rdf_repository
repo = get_rdf_repository()
print(f'Customers: {repo.count_customers()}')
print(f'Products: {repo.count_products()}')
print(f'Orders: {repo.count_orders()}')
print(f'Tickets: {repo.count_tickets()}')
"

# TTL 재생성 (CSV 변경 시)
python scripts/12_generate_mock_ttl.py

# Fuseki에 데이터 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done

# 전체 테스트
pytest -q

# UI 실행
python ui.py

# API 실행
uvicorn api:app --reload
```
