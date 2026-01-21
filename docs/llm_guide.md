# LLM Provider 설정 가이드

이 문서는 LLM (Large Language Model) Provider를 설정하고 전환하는 방법을 설명합니다.

## 지원 Provider

| Provider | 설명 | 필수 설정 |
|----------|------|----------|
| `openai` | OpenAI GPT 모델 (gpt-4o-mini 등) | `OPENAI_API_KEY` |
| `anthropic` | Anthropic Claude 모델 | `ANTHROPIC_API_KEY` |
| `google` | Google Gemini 모델 | `GOOGLE_API_KEY` |
| `local` | 로컬 LLM (vLLM, Ollama 등) | `base_url` |

---

## Provider 전환 방법

### 방법 1: 환경변수 (권장)

```bash
# OpenAI 사용
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-proj-xxx

# Anthropic 사용
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-xxx

# Google Gemini 사용
export LLM_PROVIDER=google
export GOOGLE_API_KEY=AIzaSyxxx

# 로컬 LLM 사용
export LLM_PROVIDER=local
```

### 방법 2: YAML 설정 파일

`configs/llm.yaml` 파일을 수정합니다:

```yaml
# 사용할 프로바이더 선택: openai | anthropic | google | local
provider: openai

openai:
  api_key: "sk-proj-xxx"  # 또는 환경변수 OPENAI_API_KEY 사용
  model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 1024
  timeout: 30

anthropic:
  api_key: ""  # ANTHROPIC_API_KEY 환경변수 사용
  model: claude-3-haiku-20240307
  temperature: 0.7
  max_tokens: 1024
  timeout: 30

google:
  api_key: ""  # GOOGLE_API_KEY 환경변수 사용
  model: gemini-1.5-flash
  temperature: 0.7
  max_tokens: 1024
  timeout: 30

local:
  base_url: http://localhost:8080/v1
  model: local-model
  temperature: 0.7
  max_tokens: 1024
  timeout: 60
```

---

## 설정 우선순위

1. **환경변수** (최우선)
   - `LLM_PROVIDER`: provider 선택
   - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`: API 키

2. **YAML 설정 파일** (`configs/llm.yaml`)
   - 환경변수가 없을 때 사용

---

## Provider별 상세 설정

### OpenAI

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-proj-xxx
```

**지원 모델**:
- `gpt-4o-mini` (기본, 경제적)
- `gpt-4o` (고성능)
- `gpt-4-turbo`
- `gpt-3.5-turbo`

**API 키 발급**: https://platform.openai.com/api-keys

### Anthropic (Claude)

```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-xxx
```

**지원 모델**:
- `claude-3-haiku-20240307` (기본, 빠름)
- `claude-3-sonnet-20240229` (균형)
- `claude-3-opus-20240229` (고성능)

**API 키 발급**: https://console.anthropic.com/

### Google Gemini

```bash
export LLM_PROVIDER=google
export GOOGLE_API_KEY=AIzaSyxxx
```

**지원 모델**:
- `gemini-1.5-flash` (기본, 빠름)
- `gemini-1.5-pro` (고성능)
- `gemini-2.0-flash-exp`

**API 키 발급**: https://aistudio.google.com/apikey

### Local LLM (vLLM / Ollama)

```bash
export LLM_PROVIDER=local
```

`configs/llm.yaml`에서 `base_url` 설정:

```yaml
local:
  base_url: http://localhost:8080/v1  # vLLM
  # base_url: http://localhost:11434/v1  # Ollama
  model: local-model
```

#### vLLM 실행 예시

```bash
# vLLM 서버 실행
python -m vllm.entrypoints.openai.api_server \
    --model ./outputs/merged_model \
    --port 8080

# 또는 LoRA 모드
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct \
    --enable-lora \
    --lora-modules custom=./outputs/lora_adapter \
    --port 8080
```

#### Ollama 실행 예시

```bash
# Ollama 서버 실행
ollama serve

# 모델 실행
ollama run llama3.1:8b
```

---

## LLM 호출 흐름

```
사용자 요청
    │
    ▼
┌─────────────────────────────────────┐
│ _is_llm_available() 체크           │
│ (src/agents/orchestrator.py:21)    │
└───────────────┬─────────────────────┘
                │
    ┌───────────┴───────────┐
    │                       │
LLM 사용 가능          LLM 사용 불가
    │                       │
    ▼                       ▼
LLMClient.chat()       Raw 데이터 반환
    │                  (LLM 합성 없음)
    ▼
Provider 분기
├─ openai → _chat_openai()
├─ anthropic → _chat_anthropic()
├─ google → _chat_google()
└─ local → _chat_local()
```

### LLM 사용 가능 조건

| Provider | 조건 |
|----------|------|
| `openai` | API 키가 설정되어 있음 |
| `anthropic` | API 키가 설정되어 있음 |
| `google` | API 키가 설정되어 있음 |
| `local` | `base_url`이 설정되어 있음 |

---

## Fallback 동작

LLM을 사용할 수 없는 경우 (API 키 없음, 서버 오류 등):

1. **의도 분류**: LLM 실패 시 → 키워드 기반 분류로 fallback
2. **응답 생성**: LLM 없이 → 도구 결과만 반환 (JSON 형식)

```python
# LLM 없이 반환되는 응답 예시
{
    "intent": "order",
    "data": {
        "order_id": "ORD001",
        "status": "delivered",
        ...
    }
}
```

---

## 스트리밍 지원

모든 Provider는 스트리밍 응답을 지원합니다:

```python
from src.llm import get_client

client = get_client()

# 일반 응답
response = await client.chat([{"role": "user", "content": "안녕하세요"}])

# 스트리밍 응답
async for chunk in client.chat_stream([{"role": "user", "content": "안녕하세요"}]):
    print(chunk, end="", flush=True)
```

API 엔드포인트:
- `/chat` - 일반 응답
- `/chat/stream` - SSE 스트리밍 응답

---

## 비용 비교 (참고)

| Provider | 모델 | 입력 (1M 토큰) | 출력 (1M 토큰) |
|----------|------|--------------|--------------|
| OpenAI | gpt-4o-mini | $0.15 | $0.60 |
| OpenAI | gpt-4o | $2.50 | $10.00 |
| Anthropic | claude-3-haiku | $0.25 | $1.25 |
| Anthropic | claude-3-sonnet | $3.00 | $15.00 |
| Google | gemini-1.5-flash | $0.075 | $0.30 |
| Google | gemini-1.5-pro | $1.25 | $5.00 |
| Local | - | 무료 | 무료 |

*2024년 12월 기준, 실제 가격은 공식 사이트 참조*

---

## 문제 해결

### API 키 오류

```
ValueError: API key not configured
```

**해결**: 환경변수 또는 YAML 파일에 API 키 설정

### Provider 연결 실패

```
aiohttp.ClientError: Connection refused
```

**해결**:
- 로컬 LLM: vLLM/Ollama 서버가 실행 중인지 확인
- API: 네트워크 연결 및 방화벽 확인

### 타임아웃

```
asyncio.TimeoutError
```

**해결**: `configs/llm.yaml`에서 `timeout` 값 증가

```yaml
local:
  timeout: 120  # 60 → 120초로 증가
```

---

## 관련 파일

- `configs/llm.yaml` - LLM 설정 파일
- `src/llm/client.py` - LLM 클라이언트 구현
- `src/agents/orchestrator.py` - LLM 사용 여부 결정 로직
- `.env.example` - 환경변수 템플릿

---

# 로컬 LLM 서빙/통합 가이드

## 개요

- 본 프로젝트는 기본적으로 OpenAI/Anthropic/로컬(OpenAI 호환 REST) 경로를 통해 LLM을 호출합니다.
- 로컬 학습(LoRA) 결과를 API에서 사용하려면 (A) 병합 후 서빙 또는 (B) LoRA 부착 서빙 방식을 사용합니다.

## 학습 산출물과 베이스 모델

- 베이스 모델: `beomi/Llama-3-Open-Ko-8B` (Hugging Face Hub)
- 학습 산출물(LoRA Adapter): `outputs/ecommerce-agent-qlora/`
- 베이스 가중치는 레포에 포함되지 않으므로, 아래 방법으로 준비하세요.
  - 자동 다운로드(인터넷 필요): Transformers가 최초 로드 시 자동 다운로드
  - 사전 다운로드(오프라인 준비):
    - `pip install huggingface_hub`
    - `python scripts/00_download_base_model.py --repo-id beomi/Llama-3-Open-Ko-8B --target models/beomi-Llama-3-Open-Ko-8B`

## CLI 학습/테스트

- 학습(QLoRA, 인자화됨):
```bash
python scripts/06_train_qlora.py \
  --base-model beomi/Llama-3-Open-Ko-8B \
  --data-dir data/training \
  --output-dir outputs/ecommerce-agent-qlora \
  --epochs 3 --lr 2e-4 --batch 2 --max-length 512
```
- LoRA 테스트(서버 없이):
```bash
python scripts/08_test_finetuned_model.py --lora-path outputs/ecommerce-agent-qlora [--interactive]
```

## 서빙 방식 A: 병합 후 서빙 (권장)

1) 병합: `bash scripts/07_merge_lora.sh` → `outputs/ecommerce-agent-merged/`
2) vLLM 서빙: `pip install vllm && vllm serve outputs/ecommerce-agent-merged --host 0.0.0.0 --port 8080`
3) API 연결:
   - `configs/llm.yaml`: `provider: local`, `local.base_url: http://localhost:8080/v1`, `local.model: ecommerce-agent-merged`
   - 또는 원클릭 스크립트: `bash scripts/run_local_llm_api.sh --serve outputs/ecommerce-agent-merged --llm-model ecommerce-agent-merged`

## 서빙 방식 B: LoRA 부착 서빙 (vLLM)

- vLLM 버전에 따라 옵션이 다릅니다(예: `--lora-modules name=path`). 예시:
```bash
vllm serve beomi/Llama-3-Open-Ko-8B --host 0.0.0.0 --port 8080 \
  --lora-modules ecommerce-agent=outputs/ecommerce-agent-qlora
```
- API 연결: `local.model: ecommerce-agent`
- 원클릭 스크립트: `bash scripts/run_local_llm_api.sh --serve beomi/Llama-3-Open-Ko-8B --lora outputs/ecommerce-agent-qlora --llm-model ecommerce-agent`

## API와의 통합

- `LLM_PROVIDER=local`, `LLM_MODEL=<모델명>` 환경변수를 통해 코드 변경 없이 모델 교체 가능
- 실패/타임아웃/토큰 초과 로그는 `logs/api.log` 확인

## 모델 교체 체크리스트

- [ ] 베이스/병합 모델 경로 혹은 Repo ID 준비
- [ ] vLLM 설치 및 실행 확인
- [ ] `configs/llm.yaml` 또는 환경변수로 모델명/엔드포인트 반영
- [ ] `bash scripts/smoke_api.sh`로 스모크 패스 확인

---

# LibreChat / OpenWebUI 연동 가이드

## 개요

- LibreChat/OpenWebUI는 OpenAI-호환 API를 호출하는 범용 챗 UI입니다. 본 프로젝트에서는 다음 두 방식으로 연결할 수 있습니다.
  1) 모델 품질 확인(간단): LibreChat → vLLM(8080)
  2) 오케스트레이터 사용: LibreChat → 우리 API `/v1/chat/completions`(8000)

## 포트 권장

| 서비스 | 포트 | 설정 위치 |
|--------|------|-----------|
| API (FastAPI) | 8000 | `configs/app.yaml` → `server.port` |
| vLLM (로컬 LLM) | 8080 | - |
| LibreChat | 3100 | 컨테이너 3080 → 호스트 3100 매핑 |
| OpenWebUI | 3000 | - |

## 방식 1: vLLM 직결 (간단)

1. vLLM 실행 (병합 모델 기준):
```bash
vllm serve outputs/ecommerce-agent-merged --host 0.0.0.0 --port 8080
```

2. LibreChat Provider (OpenAI) 설정:
- Base URL: `http://host.docker.internal:8080/v1` (Linux에서는 호스트 IP 사용)
- API Key: `sk-local` (임의 문자열)
- 모델명: `ecommerce-agent-merged`

## 방식 2: 오케스트레이터 경유

1. `configs/app.yaml`에서 OpenAI-호환 레이어 활성화:
```yaml
openai_compat:
  enabled: true
  mode: orchestrator    # 또는 passthrough
  require_api_key: false
```

2. API 실행: `python scripts/serve_api.py`

3. LibreChat Provider (OpenAI) 설정:
- Base URL: `http://host.docker.internal:8000/v1`
- API Key: (require_api_key=true일 때 allowed_keys에 등록한 값)
- 모델명: `ecommerce-agent-merged` (또는 configs/llm.yaml의 model)

## OpenWebUI 실행

```bash
docker run -d -p 3000:3000 \
  -e OPENAI_API_BASE_URL=http://host.docker.internal:8000/v1 \
  -e OPENAI_API_KEY=sk-local \
  ghcr.io/open-webui/open-webui:main
```

접속: http://localhost:3000

## 검증

- 대화 입력 시, orchestrator 모드에서는 정책/주문/티켓 도구/가드레일이 반영된 응답을 반환합니다.
- passthrough 모드에서는 순수 LLM 응답 품질 확인용입니다.

## 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| 404 (not enabled) | `openai_compat.enabled`가 false | `configs/app.yaml`에서 true로 변경 |
| 401 | require_api_key=true인데 키 미등록 | allowed_keys에 키 추가 |
| 5xx | LLM 연결/오케스트레이터 예외 | `logs/api.log` 확인 |
