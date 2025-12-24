# 정책(FAQ/환불/배송) 파이프라인 가이드

## 개요
- 정책/FAQ 문서를 경량 수집/정규화하여 로컬 인덱스(JSONL)로 구축하고 검색합니다.
- 초기에는 로컬 HTML 파일로 파서를 검증한 뒤, 도메인 화이트리스트를 정해 제한적 네트워크 수집으로 확장할 수 있습니다.

## 단계
1) 수집/정규화: `scripts/01a_crawl_policies.py`
   - 입력: 환경변수 `POLICY_LOCAL_HTML`에 로컬 HTML 경로(콤마 구분) 지정 가능
   - 출력: `data/processed/policies.jsonl` (필드: url, title, content, doc_type, source)
2) 인덱싱: `scripts/04_build_index.py`
   - 입력: `data/processed/policies.jsonl`
   - 출력: `data/processed/policies_index.jsonl` (청크 분할 + 메타데이터)
3) 검색: `src/rag/retriever.py`
   - 간단 토큰 기반 점수(TF/길이 보정)로 상위 K를 반환

## 권장 운영 원칙
- robots.txt/약관 준수, 내부 PoC 용도 한정
- 수집일/출처 기록, 중복/오래된 정보 정리
- 실패 대비: 셀렉터 파손 시 태그 제거 기반 텍스트 추출로 폴백

## 통합 포인트
- API: `GET /policies/search?q=...`
- Guardrails(후속): 정책 준수 검증 시 정책 리트리버를 참조하여 근거 문구/링크 포함

