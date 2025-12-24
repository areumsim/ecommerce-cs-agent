RAG 개선 계획 및 가이드
===================

현황 요약
--------
- 텍스트 인덱스(JSONL) 기반 키워드 검색이 기본이며, FAISS/임베딩 파일이 존재하면 임베딩/하이브리드 검색 사용
- FAISS 미설치 또는 벡터 인덱스 미존재 시 자동 키워드 폴백

권장 설치/활성화
-------------
- faiss 설치: `pip install faiss-cpu`
- 임베딩/벡터 인덱스 생성: `python scripts/04_build_index.py` (기본 설정은 configs/rag.yaml 참조)
- 리트리버는 자동으로 모드를 선택(embedding/hybrid 설정 시)

간단 리랭커 추가(제안)
------------------
1) BM25 키워드 Top-N 또는 하이브리드 Top-N을 2차 후보로 수집
2) 경량 크로스-인코더(영문/다국어 지원) 또는 간단 스코어 휴리스틱으로 재정렬
3) 최종 Top-K 반환

구현 포인트(제안 인터페이스)
-------------------------
- 위치: `src/rag/retriever.py`에 `rerank_hits(hits: List[PolicyHit]) -> List[PolicyHit]` 훅 추가
- 설정: `configs/rag.yaml`에 `retrieval.use_reranking: true`, `retrieval.reranker: <name>`
- 기본 구현: 휴리스틱(쿼리 토큰 가중치, 타이틀 우선), 선택 구현: cross-encoder(작은 모델)

품질 측정/스모크
-------------
- 샘플 쿼리 세트(환불/배송/취소/불량/FAQ)를 만들어 Top-1 정확도/정상성 점검
- 스모크 스크립트에 간단한 품질 어서션(최소 스코어/문서 개수) 옵션 추가 검토

