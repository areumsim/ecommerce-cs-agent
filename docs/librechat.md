LibreChat 연동 가이드
=================

개요
---
- LibreChat은 OpenAI-호환 API를 호출하는 범용 챗 UI입니다. 본 프로젝트에서는 다음 두 방식으로 연결할 수 있습니다.
  1) 모델 품질 확인(간단): LibreChat → vLLM(8080)
  2) 오케스트레이터 사용: LibreChat → 우리 API `/v1/chat/completions`(8000)

포트 권장
------
- API(FastAPI): 8000 (configs/app.yaml → server.port)
- vLLM(로컬 LLM): 8080
- LibreChat: 3100 (컨테이너 3080을 호스트 3100으로 매핑)

1) vLLM 직결(간단)
----------------
1. vLLM 실행(병합 모델 기준):
```
vllm serve outputs/ecommerce-agent-merged --host 0.0.0.0 --port 8080
```
2. LibreChat Provider(OpenAI) 설정:
- Base URL: `http://host.docker.internal:8080/v1` (Linux에서는 호스트 IP 사용)
- API Key: `sk-local` (임의 문자열)
- 모델명: `ecommerce-agent-merged`

2) 오케스트레이터 경유(선택지 B)
---------------------------
1. configs/app.yaml에서 OpenAI-호환 레이어 활성화:
```
openai_compat:
  enabled: true
  mode: orchestrator    # 또는 passthrough
  require_api_key: false
```
2. API 실행: `python scripts/serve_api.py`
3. LibreChat Provider(OpenAI) 설정:
- Base URL: `http://host.docker.internal:8000/v1`
- API Key: (require_api_key=true일 때 allowed_keys에 등록한 값)
- 모델명: `ecommerce-agent-merged` (또는 configs/llm.yaml의 model)

검증
---
- 대화 입력 시, orchestrator 모드에서는 정책/주문/티켓 도구/가드레일이 반영된 응답을 반환합니다.
- passthrough 모드에서는 순수 LLM 응답 품질 확인용입니다.

문제 해결
------
- 404(not enabled): `openai_compat.enabled`가 false입니다.
- 401: require_api_key=true인데 키가 없거나 allowed_keys에 미등록입니다.
- 5xx: `logs/api.log` 확인(LLM 연결/오케스트레이터 예외)
