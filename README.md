🛒 Ecommerce Agent (PoC)
=======================

한국어 기반 상품 상담·주문/클레임 지원 에이전트 PoC입니다. CSV-우선(Mock) 저장소로 빠르게 검증하되, 필요 시 SQLite 백엔드로 전환할 수 있습니다. 정책(FAQ/환불/배송) 검색은 로컬 인덱스(텍스트+벡터) 기반입니다.

기능 개요
--------
- 대화/챗 인터페이스(의도 분류 → 오케스트레이터 → 도구 호출)
- 주문: 목록/상세/상태/취소(Mock CSV/SQLite)
- 클레임: 티켓 생성/조회/해결(Mock CSV/SQLite)
- 정책 검색: 텍스트/벡터/하이브리드 검색(FAISS 선택적)
- 인증: 이메일/비밀번호 기반 JWT 발급 및 보호 엔드포인트
- 대화 세션: 다중 턴 히스토리 관리(Conversation API)
- 모니터링: `/metrics`(Prometheus), `/health`, `/ready`
- UI: Gradio 데모, API: FastAPI 엔드포인트

폴더 구조(요약)
------------
- `configs/` — 환경설정(`mock.yaml` 등)
- `data/` — 원천/가공/Mock 데이터(CSV/JSONL)
- `scripts/` — 데이터 수집·가공·인덱싱·E2E 스크립트
- `src/` — 서비스/도구/노드/오케스트레이터/RAG
- `api.py` — FastAPI 서버
- `ui.py` — Gradio 데모 UI
- `PRD.md` — Phase 1 PRD(범위/수용기준)
- `AGENTS.md` — 리포지토리 기여/개발 가이드
- `TODO.md` — 구현 가이드/체크리스트

자세한 CSV/SQLite 스키마와 파이프라인은 `docs/mock_storage.md`, `docs/policy_pipeline.md` 참고.

진행 상황 요약 (2025-12)
--------

- 데이터 전처리: 완료 (products/reviews parquet 산출물 존재)
- Mock CSV 저장소: 완료 (8개 테이블), SQLite 마이그레이션 스크립트 제공
- API 엔드포인트: 정책/주문/티켓/챗 외에 인증/대화/모니터링/비전 포함
- 정책 RAG: 텍스트 인덱스+선택적 벡터 인덱스(FAISS) 및 하이브리드 검색 지원
- Orchestrator: LLM 클라이언트 통합(옵션), 가드레일 파이프라인 연동
- 테스트: pytest 스위트 포함(여러 영역 커버). 로컬 환경에서 실행해 검증 권장
- 파인튜닝: LoRA 아답터 산출물/스크립트 포함(선택 사항, GPU 필요)

### 현재 한계점
- 의도 분류가 정규식+키워드 중심(LLM 분류 백업 사용 가능)
- 벡터 검색/리랭킹은 선택적 구성(FAISS/추가 리랭커 미설치 시 키워드로 폴백)
- 파인튜닝 모델은 예시 수준(데이터셋 확장/평가 자동화 필요)

- 데이터 전처리 완료: `scripts/02_full_preprocess_stream.py` 수행
  - 생성물: `data/processed/products.parquet`(~203MB), `reviews.parquet`(~7.5GB), `reviews_agg.parquet`(~19MB)

빠른 시작
--------
1) 정책 데이터 준비(로컬 HTML로도 가능)

```
python scripts/01a_crawl_policies.py
python scripts/04_build_index.py
```

2) CSV 시드/특성 반영(샘플 포함)

```
 python scripts/03_generate_mock_csv.py
```

3) (선택) CSV→SQLite 마이그레이션 및 API 실행

SQLite로도 사용하려면:

```
python scripts/05_migrate_to_sqlite.py  # data/ecommerce.db 생성/갱신
```

API 실행:

```
 python scripts/serve_api.py   # 기본 포트는 configs/app.yaml의 server.port(기본 8000)
```

4) UI 실행(선택)

```
 python ui.py

스모크 체크(자동)
------------
```
# .env 파일에서 APP_PORT 설정 가능(.env.example 참고)
# 또는 환경변수로 지정 후 실행
APP_PORT=${APP_PORT:-8000}

bash scripts/smoke_api.sh           # 기본: http://localhost:8000, "환불"
# .env 파일에서 APP_PORT 설정 가능(.env.example 참고)
# 또는 환경변수로 지정 후 실행
APP_PORT=${APP_PORT:-8000}

bash scripts/smoke_api.sh http://localhost:8000 배송  # 커스텀
# 포트 포워딩(예: 19004->8000)이 설정된 환경에서는:
# .env 파일에서 APP_PORT 설정 가능(.env.example 참고)
# 또는 환경변수로 지정 후 실행
APP_PORT=${APP_PORT:-8000}

bash scripts/smoke_api.sh http://localhost:19004 환불
```

시나리오용 실데이터 시딩
-------------------
- 제품 캐시(실데이터 전체):
```
python scripts/03_generate_mock_csv.py --limit 0 --no-orders
```
- PRD 시나리오 최소 주문/아이템(실데이터 기반 제품 참조):
```
python scripts/03a_seed_scenarios.py --user user_001 --with-ticket
```
```

주요 엔드포인트
-------------
- 헬스/모니터링: `GET /healthz`, `GET /health`, `GET /ready`, `GET /metrics`
- 인증(JWT):
  - `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/logout`
- 정책 검색: `GET /policies/search?q=...&top_k=5`
- 주문:
  - `GET /users/{user_id}/orders?status=&limit=`
  - `GET /orders/{order_id}`
  - `GET /orders/{order_id}/status`
  - `POST /orders/{order_id}/cancel` body: `{"reason":"..."}`
- 티켓:
  - `POST /tickets` body: `{user_id, order_id?, issue_type, description, priority}`
  - `GET /tickets/{ticket_id}`
  - `GET /users/{user_id}/tickets?status=&limit=`
  - `POST /tickets/{ticket_id}/resolve`
- 대화 세션(보호):
  - `POST /conversations`, `GET /conversations`, `GET /conversations/{id}`
  - `POST /conversations/{id}/messages`
- 비전: `POST /vision/analyze`, `POST /vision/defect`
- 챗: `POST /chat` body: `{user_id, message}`

스토리지 구성
-----------
- CSV(Mock): `data/mock_csv/*` / `configs/mock.yaml` (`storage_backend: csv`)
- SQLite: `data/ecommerce.db` / `configs/paths.yaml` (`storage.backend: sqlite`)
- 구현: `src/mock_system/storage/csv_repository.py`, `src/mock_system/storage/sqlite_repository.py`
- 주의: CSV는 단일-라이터 권장(파일 락 미구현)

정책 파이프라인
-------------
- 수집/정규화: `scripts/01a_crawl_policies.py` → `data/processed/policies.jsonl`
- 인덱싱: `scripts/04_build_index.py` → 텍스트(`policies_index.jsonl`) + (선택)벡터(`policies_vectors.faiss`)
- 검색: `src/rag/retriever.py` (keyword/embedding/hybrid, FAISS 미설치·벡터 없음 시 자동 폴백)

검증 방법
--------
- 스모크: `# .env 파일에서 APP_PORT 설정 가능(.env.example 참고)
# 또는 환경변수로 지정 후 실행
APP_PORT=${APP_PORT:-8000}

bash scripts/smoke_api.sh`
- E2E: `python scripts/08_e2e_order_claim.py`
- API TestClient(포트 없이):
```python
from fastapi.testclient import TestClient
from api import app
c = TestClient(app)
assert c.get('/healthz').status_code == 200
assert c.get('/policies/search', params={'q':'refund','top_k':3}).status_code == 200
```
- **UI 확인**: `python ui.py`

테스트 실행
--------
- 의존성 설치:
```
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```
- 전체 테스트:
```
pytest -q
```
- 특정 파일/테스트만:
```
pytest tests/test_api.py -q
pytest -k "guardrails and not slow" -q
```
- 오프라인 실행 팁:
  - LLM 호출 비활성화를 위해 `configs/llm.yaml` 기본값을 유지하세요(provider=openai, api_key 비워둠). 키가 없으면 LLM은 호출되지 않습니다.
  - FAISS 미설치/벡터 미존재 시 검색은 키워드 모드로 자동 폴백됩니다.

원클릭 로컬 LLM+API 실행 (포트는 configs/app.yaml 기준)
--------------------
vLLM을 이용해 로컬 모델을 서빙하고 API를 동시에 띄운 뒤 스모크 테스트까지 수행합니다.

```
bash scripts/run_local_llm_api.sh --serve outputs/ecommerce-agent-merged --llm-model ecommerce-agent-merged
# LoRA를 베이스에 붙여서 서빙할 때(버전별 옵션 상이 가능):
bash scripts/run_local_llm_api.sh --serve beomi/Llama-3-Open-Ko-8B --lora outputs/ecommerce-agent-qlora --llm-model ecommerce-agent
```

전제: `pip install vllm`가 설치되어 있어야 하며, 필요 시 병합 스크립트(`scripts/07_merge_lora.sh`)로 병합 모델을 만든 뒤 `--serve`에 경로를 넣어주세요.


개발 워크플로우
------------
- 설계/범위: `PRD.md` 기준, 기여/규칙은 `AGENTS.md` 참조
- 구현 체크리스트: `TODO.md` 진행사항 반영
- 단계별: 데이터→Mock/SQLite→RAG→Agent→API→UI 순서로 통합
- 수용 기준: PRD의 수용 기준 + 스모크/E2E 통과

참고 문서
--------
- API 레퍼런스: `docs/api_reference.md`
- LLM Provider 가이드: `docs/llm_guide.md`
- 비전 파이프라인: `docs/vision_guide.md`
- 설정 파일 레퍼런스: `docs/configuration.md`
- 로컬 LLM 서빙/통합: `docs/local_llm.md`
- RAG 개선 가이드: `docs/rag_improvements.md`
- 운영/배포 가이드: `docs/operations.md`

미비점 및 개선 계획
--------------
- RAG 개선: `faiss-cpu` 설치 후 하이브리드/임베딩 활성화, 간단 리랭커(휴리스틱 또는 경량 cross-encoder) 추가
- LLM 경로 고도화: 로컬 LoRA 서빙(vLLM/TGI) 또는 `src/llm/client.py`에 HF 로컬 로딩 경로 추가하여 API에서 학습 모델 직접 사용
- 데이터/평가: 정책/주문/클레임 데이터 확장 + 자동 평가 스크립트 작성, 실패 케이스 회귀 테스트 보강
- 운영성: CSV→SQLite 전환 검토(`scripts/05_migrate_to_sqlite.py`), `/metrics` 대시보드 구성
- 리랭커/고급 검색: 별도 리랭커 미구현(하이브리드/임베딩은 제공, FAISS 설치 시 고도화 가능)
- LLM 운영 경로: API 런타임은 OpenAI/Anthropic/REST-호환(Local)만 호출. 로컬 HF 모델(LoRA) 직접 로딩은 테스트 스크립트에 한정(서비스 경로 미통합)
- 파일 동시성: CSV는 파일 락 미구현(단일-라이터 권장)
- 비전: 경량 분석(use_clip=False) 중심. 대형/고정밀 파이프라인은 범위 외

LLM 라우팅(의도/도메인 기반)
----------------------
- 목적: 판매/정책/CS(정책/주문/클레임)는 "학습된 로컬 LLM", 일반/상품정보는 "외부 LLM API" 경로로 자동 라우팅.
- 설정: `configs/llm.yaml`에 `routing` 블록.
```
routing:
  enabled: true
  rules:
    - when: { intents: ["policy", "claim", "order"] }
      provider: local
    - when: { intents: ["general", "product_info", "unknown"] }
      provider: openai
  fallback: { provider: openai }
```
- 동작: 오케스트레이터에서 LLM 호출 시 `src/llm/router.py`가 intent별 provider를 선택하여 호출.
- 가드레일: 입력/출력 전체에 적용(process_input/apply_guards). 욕설/비난/PII/인젝션은 차단 혹은 정중 거절.



LLM 설정
--------
- `configs/llm.yaml`에서 프로바이더/모델/토큰/타임아웃을 설정합니다.
- 환경변수로 오버라이드 가능: `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 등
- 프롬프트 경로: `configs/prompts/*.txt` (system/order/claim/policy 등)

OpenAI 호환 레이어
----------------
외부 UI(LibreChat, OpenWebUI 등)와 연동을 위한 OpenAI 호환 API를 제공합니다.

### 활성화
`configs/app.yaml`에서:
```yaml
openai_compat:
  enabled: true           # 활성화
  mode: orchestrator      # orchestrator | passthrough
  require_api_key: false  # API 키 필수 여부
  default_model: "ecommerce-agent-merged"
```

### 엔드포인트
- `GET /v1/models` - 모델 목록
- `POST /v1/chat/completions` - 채팅 완성 (스트리밍 지원)

### 스모크 테스트
```bash
# API 서버 실행
python scripts/serve_api.py

# 테스트
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"환불 정책 알려줘"}]}'
```

### LibreChat 연동
1. API 서버 실행: `python scripts/serve_api.py` (포트 8000)
2. LibreChat Admin → Provider 설정:
   - Base URL: `http://host.docker.internal:8000/v1` (Docker) 또는 `http://localhost:8000/v1`
   - API Key: 임의값 (require_api_key=false인 경우)
   - Model: `ecommerce-agent-merged`

### OpenWebUI 연동
```bash
docker run -d -p 3000:3000 \
  -e OPENAI_API_BASE_URL=http://host.docker.internal:8000/v1 \
  -e OPENAI_API_KEY=sk-local \
  ghcr.io/open-webui/open-webui:main
```
접속: http://localhost:3000

### vLLM 직접 연결 (모델 품질만 확인)
```bash
# vLLM 서버 실행
vllm serve outputs/ecommerce-agent-merged --host 0.0.0.0 --port 8080

# LibreChat/OpenWebUI에서:
# Base URL: http://host.docker.internal:8080/v1
# API Key: sk-local (임의값)
```

다음 단계(권장)
-----------
1) LLM 분류/응답 품질 개선(리랭커/시맨틱 강화, 평가 자동화)
2) 스토리지 추상화 정리 및 DB 전환 스크립트 고도화
3) UI 데모 개선(카드/액션 버튼), 모니터링 대시보드 추가

파인튜닝 모델 사용(선택)
------------------
```bash
# 파인튜닝 모델 테스트
python scripts/08_test_finetuned_model.py --lora-path outputs/ecommerce-agent-qlora

# 대화형 모드
python scripts/08_test_finetuned_model.py --lora-path outputs/ecommerce-agent-qlora --interactive
```

파인튜닝/모델 자산
---------------
- 베이스 모델: `beomi/Llama-3-Open-Ko-8B` (Hugging Face Hub)
- 산출물(LoRA 어댑터): `outputs/ecommerce-agent-qlora/` (adapter_model.safetensors 등)
- 주의: 베이스 가중치는 레포에 포함되지 않습니다. 아래 중 하나를 선택하세요.
  - A) Transformers 자동 다운로드(인터넷/HF 토큰 필요)
  - B) 사전 다운로드: `pip install huggingface_hub` 후
    - `python scripts/00_download_base_model.py --repo-id beomi/Llama-3-Open-Ko-8B --target models/beomi-Llama-3-Open-Ko-8B`

로컬 서빙 옵션
------------
- 병합 후 서빙(권장):
  - `bash scripts/07_merge_lora.sh`  # 베이스+LoRA 병합 → `outputs/ecommerce-agent-merged/`
  - vLLM 예시: `pip install vllm && vllm serve outputs/ecommerce-agent-merged --host 0.0.0.0 --port 8080`
  - `configs/llm.yaml`: `provider: local`, `local.base_url: http://localhost:8080/v1`, `local.model: ecommerce-agent-merged`
- 병합 없이 LoRA 서빙(vLLM LoRA 모드): vLLM 버전에 따라 `--lora-modules` 옵션 사용(서버 문서 참고).

보안/시크릿
---------
- API 키·토큰은 코드/레포에 포함하지 마세요(.env/비밀관리 사용).
- 이미 노출된 자격증명이 있다면 즉시 폐기/교체하세요.

향후 고도화(발췌)
--------------
- 리랭커/하이브리드 검색 강화, 평가 지표 확장
- DB 전환(SQL 저장소 구현) 및 안정적 마이그레이션
- UI 액션 버튼/카드 고도화, 자동 평가/리포트

인증 흐름 예시
-----------
- 회원가입:
```
curl -s -X POST http://localhost:8000/auth/register \
 -H 'Content-Type: application/json' \
 -d '{"email":"test@example.com","password":"Passw0rd!","name":"Tester"}'
```
- 로그인(토큰 발급):
```
curl -s -X POST http://localhost:8000/auth/login \
 -H 'Content-Type: application/json' \
 -d '{"email":"test@example.com","password":"Passw0rd!"}'
```
응답의 `access_token`을 `TOKEN`으로 저장 후 보호 엔드포인트 호출:
```
export TOKEN=... # 위 응답값
curl -s http://localhost:8000/conversations \
 -H "Authorization: Bearer $TOKEN"
```


LibreChat/OpenWebUI 연동
--------------------
- 목적: 외부 UI에서 모델/대화 품질 확인. 기본은 vLLM(OpenAI-호환) 직결.
- LibreChat (권장 포트 3100):
  - docker-compose(공식)로 MongoDB/Redis 포함 기동 후, OPENAI_BASE_URL=http://host.docker.internal:8080/v1, OPENAI_API_KEY=sk-local 설정
  - 브라우저: http://localhost:3100
- OpenWebUI (나중에 교체 시, 권장 포트 3000):
  - docker run -d -p 3000:3000 -e OPENAI_API_BASE_URL=http://host.docker.internal:8080/v1 -e OPENAI_API_KEY=sk-local ghcr.io/open-webui/open-webui:main
  - 브라우저: http://localhost:3000

오케스트레이터 연동(선택지 B)
-------------------------
- 우리 API에 OpenAI-호환 레이어를 추가했습니다(토글). configs/app.yaml:
```
openai_compat:
  enabled: false            # true로 켜면 /v1/models, /v1/chat/completions 활성화
  mode: orchestrator        # orchestrator | passthrough
  require_api_key: false
  allowed_keys: []
```
- orchestrator: UI(LibreChat/OpenWebUI)가 /v1/chat/completions로 요청하면 내부에서 의도 분류→도구 호출→가드레일을 적용해 응답(OpenAI 포맷) 반환
- passthrough: LLM 호출을 그대로 전달(모델 품질 확인용)
- 스모크(cURL):
```
curl -s -X POST http://localhost:8000/v1/chat/completions  -H 'Content-Type: application/json'  -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"환불 정책 알려줘"}]}' | jq .choices[0].message.content
```
