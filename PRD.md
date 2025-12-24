## PRD: 한국어 전자상거래 상담·주문/클레임 PoC (Phase 1)

### 목적과 범위
- 목적: CSV-우선(Mock) 저장소와 로컬 정책 인덱스를 활용해 주문/클레임/정책 질의의 E2E 경험을 검증한다.
- 범위: 주문 목록/상세/상태/취소, 클레임 생성/조회, 정책 검색(QA), 간단 대화/오케스트레이션, 기본 인증/JWT, 대화 세션, 모니터링. (고급 리랭킹/외부 DB 연계/프로덕션 배포는 범위 외)

### 현재 진행 상황(2025-12)

코드 기준으로 다음 영역이 구현되어 있다.
- 전처리/데이터: `data/processed/*.parquet` 산출물 존재, 정책 JSONL/인덱스 포함
- 스토리지: CSV 8테이블 + SQLite 마이그레이션 스크립트(`scripts/05_migrate_to_sqlite.py`)
- API: 정책/주문/티켓/챗 + 인증/대화/모니터링/비전 엔드포인트 구현
- RAG: 텍스트 인덱스 + (선택)벡터 인덱스, 하이브리드 검색 및 폴백
- Orchestrator: LLM 클라이언트 연동(옵션) 및 가드레일 파이프라인 적용
- 테스트: pytest 스위트 제공(다수 영역 커버). 로컬에서 실행해 통과 여부 확인 필요
- 파인튜닝: LoRA 아답터/스크립트 포함(선택, GPU 필요)

### 사용자 시나리오(Phase 1)
- 주문: 사용자 주문 목록/상세/상태 조회, 취소 요청(사유 포함)
- 클레임: 티켓 생성/조회(우선순위/상태)
- 정책: 환불/배송/FAQ 검색 결과와 근거 스니펫/메타데이터 제공
- 대화: 의도 분류 → 도구 호출 → 컨텍스트+가드레일 반영 응답
- 인증/대화 세션: JWT 로그인 후 보호된 대화 API로 히스토리 관리

### 기능 요구사항(요약)
- 정책 검색: `GET /policies/search?q&top_k` → 상위 K, `text/metadata/score`
- 주문: 목록/상세/상태/취소 API 제공, 상태 전이 규칙(Mock) 적용
- 클레임: `POST /tickets`, `GET /tickets/{id}` 필수 필드 검증
- 챗: `POST /chat` 입력 → 의도 분류/오케스트레이션/가드레일 처리 결과 반환
- 인증: `POST /auth/login`으로 토큰 발급, 보호 엔드포인트는 `Authorization: Bearer` 필요
- 대화: `POST /conversations` 등 보호 엔드포인트로 세션 생성/목록/상세/메시지 추가

### 비기능 요구사항(NFR)
- 성능(로컬): p95 정책 검색 ≤1.5s, 주문/티켓 ≤1.0s (FAISS/임베딩 미구성 시 키워드로 폴백)
- 신뢰성: CSV는 단일 라이터, tmp→rename, 간단 스냅샷 옵션; SQLite는 기본 제약 검증
- 보안: 비밀정보 미커밋, PII 마스킹, `.env` 사용, JWT 만료/갱신 지원
- 관측성: `/metrics`(Prometheus), `/health`/`/ready` 제공, 요청/오류 로깅

### 수용 기준
- 정책 검색 결과에 최소 1개 이상 근거 스니펫과 메타데이터 포함
- 주문 취소 전이 규칙 준수(이미 배송완료 등 불가 상태는 차단) 및 저장소 반영
- 티켓 생성 즉시 조회 가능, 필수 필드 누락 시 4xx
- 챗 엔드포인트가 미지정 의도 시 정책 검색으로 폴백하고 정상 응답
- 스모크 시나리오 5건(헬스/검색/주문/취소/클레임) 연속 200

### 실행/검증 절차
- 정책 크롤/인덱싱: `python scripts/01a_crawl_policies.py && python scripts/04_build_index.py`
- (선택) CSV→SQLite: `python scripts/05_migrate_to_sqlite.py`
- API 실행: `uvicorn api:app --reload`
- 스모크: `bash scripts/smoke_api.sh` (기본: `http://localhost:8000`, `환불`)
- UI(선택): `python ui.py`
- 테스트: `pytest -q` (로컬 환경에서 실행)
- (선택) 파인튜닝 모델 검증:
  - 베이스 모델: `beomi/Llama-3-Open-Ko-8B` (HF Hub, 레포 미포함)
  - 사전 다운로드(옵션): `python scripts/00_download_base_model.py --repo-id beomi/Llama-3-Open-Ko-8B --target models/beomi-Llama-3-Open-Ko-8B`
  - LoRA 테스트: `python scripts/08_test_finetuned_model.py --lora-path outputs/ecommerce-agent-qlora [--interactive]`

### 제외 범위(Out of Scope)
- 외부 결제/배송사 API 연동, 정식 다중 사용자 동시성 처리, RBAC/관리자 콘솔, 클라우드 배포 템플릿

### 다음 단계(권장)
1) 리랭커/시맨틱 검색 강화 및 평가 자동화
2) 스토리지 추상화/DB 전환 스크립트 고도화 및 마이그레이션 검증
3) 대화 UI 개선, 모니터링 대시보드, 가드레일 규칙 정밀화

참고: 개발 규칙과 구조는 `AGENTS.md`, 저장소/파이프라인 상세는 `docs/` 참조.
