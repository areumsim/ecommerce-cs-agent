로컬 LLM 서빙/통합 가이드
======================

개요
---
- 본 프로젝트는 기본적으로 OpenAI/Anthropic/로컬(OpenAI 호환 REST) 경로를 통해 LLM을 호출합니다.
- 로컬 학습(LoRA) 결과를 API에서 사용하려면 (A) 병합 후 서빙 또는 (B) LoRA 부착 서빙 방식을 사용합니다.

학습 산출물과 베이스 모델
------------------
- 베이스 모델: `beomi/Llama-3-Open-Ko-8B` (Hugging Face Hub)
- 학습 산출물(LoRA Adapter): `outputs/ecommerce-agent-qlora/`
- 베이스 가중치는 레포에 포함되지 않으므로, 아래 방법으로 준비하세요.
  - 자동 다운로드(인터넷 필요): Transformers가 최초 로드 시 자동 다운로드
  - 사전 다운로드(오프라인 준비):
    - `pip install huggingface_hub`
    - `python scripts/00_download_base_model.py --repo-id beomi/Llama-3-Open-Ko-8B --target models/beomi-Llama-3-Open-Ko-8B`

CLI 학습/테스트
-------------
- 학습(QLoRA, 인자화됨):
```
python scripts/06_train_qlora.py \
  --base-model beomi/Llama-3-Open-Ko-8B \
  --data-dir data/training \
  --output-dir outputs/ecommerce-agent-qlora \
  --epochs 3 --lr 2e-4 --batch 2 --max-length 512
```
- LoRA 테스트(서버 없이):
```
python scripts/08_test_finetuned_model.py --lora-path outputs/ecommerce-agent-qlora [--interactive]
```

서빙 방식 A: 병합 후 서빙(권장)
------------------------
1) 병합: `bash scripts/07_merge_lora.sh` → `outputs/ecommerce-agent-merged/`
2) vLLM 서빙: `pip install vllm && vllm serve outputs/ecommerce-agent-merged --host 0.0.0.0 --port 8080`
3) API 연결:
   - `configs/llm.yaml`: `provider: local`, `local.base_url: http://localhost:8080/v1`, `local.model: ecommerce-agent-merged`
   - 또는 원클릭 스크립트: `bash scripts/run_local_llm_api.sh --serve outputs/ecommerce-agent-merged --llm-model ecommerce-agent-merged`

서빙 방식 B: LoRA 부착 서빙(vLLM)
---------------------------
- vLLM 버전에 따라 옵션이 다릅니다(예: `--lora-modules name=path`). 예시:
```
vllm serve beomi/Llama-3-Open-Ko-8B --host 0.0.0.0 --port 8080 \
  --lora-modules ecommerce-agent=outputs/ecommerce-agent-qlora
```
- API 연결: `local.model: ecommerce-agent`
- 원클릭 스크립트: `bash scripts/run_local_llm_api.sh --serve beomi/Llama-3-Open-Ko-8B --lora outputs/ecommerce-agent-qlora --llm-model ecommerce-agent`

API와의 통합
-----------
- `LLM_PROVIDER=local`, `LLM_MODEL=<모델명>` 환경변수를 통해 코드 변경 없이 모델 교체 가능
- 실패/타임아웃/토큰 초과 로그는 `logs/api.log` 확인

모델 교체 체크리스트
-----------------
- [ ] 베이스/병합 모델 경로 혹은 Repo ID 준비
- [ ] vLLM 설치 및 실행 확인
- [ ] `configs/llm.yaml` 또는 환경변수로 모델명/엔드포인트 반영
- [ ] `bash scripts/smoke_api.sh`로 스모크 패스 확인

