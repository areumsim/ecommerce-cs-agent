#!/usr/bin/env bash
set -euo pipefail

# One-touch launcher for local LLM (vLLM) + API + smoke test.

SERVE=""
LORA=""
LLM_MODEL="ecommerce-agent-merged"
LLM_PORT=8080
APP_PORT=8000
HOST="0.0.0.0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --serve) SERVE="$2"; shift 2;;
    --lora) LORA="$2"; shift 2;;
    --llm-model) LLM_MODEL="$2"; shift 2;;
    --llm-port) LLM_PORT="$2"; shift 2;;
    --api-port) APP_PORT="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    *) echo "[ERR] Unknown arg: $1" >&2; exit 1;;
  esac
done

if [[ -z "${SERVE}" ]]; then
  echo "[ERR] --serve (model path or repo id) is required" >&2
  exit 1
fi

mkdir -p logs

if ! command -v vllm >/dev/null 2>&1; then
  echo "[ERR] vLLM not found. Install: pip install vllm" >&2
  exit 1
fi

echo "[vLLM] Serving '${SERVE}' on ${HOST}:${LLM_PORT}"
VLLM_CMD=(vllm serve "${SERVE}" --host "${HOST}" --port "${LLM_PORT}")

if [[ -n "${LORA}" ]]; then
  echo "[vLLM] Attaching LoRA from: ${LORA}"
  VLLM_CMD+=(--lora-modules "ecommerce-agent=${LORA}")
  LLM_MODEL="ecommerce-agent"
fi

set +e
pkill -f "vllm serve" >/dev/null 2>&1 || true
pkill -f "uvicorn api:app" >/dev/null 2>&1 || true
set -e

"${VLLM_CMD[@]}" > logs/vllm.log 2>&1 &
VLLM_PID=$!
echo "[vLLM] PID=${VLLM_PID} (logs/vllm.log)"

echo "[wait] Waiting for vLLM to be ready..."
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:${LLM_PORT}/v1/models" || true)
  if [[ "${code}" == "200" ]]; then
    echo "[ok] vLLM ready"
    break
  fi
  if [[ "${i}" == "60" ]]; then
    echo "[ERR] vLLM not ready after 60s" >&2
    tail -n 100 logs/vllm.log || true
    exit 1
  fi
  sleep 1
done

export LLM_PROVIDER=local
export LLM_MODEL="${LLM_MODEL}"

echo "[API] Starting FastAPI on ${HOST}:${APP_PORT}"
uvicorn api:app --host "${HOST}" --port "${APP_PORT}" --reload > logs/api.log 2>&1 &
API_PID=$!
echo "[API] PID=${API_PID} (logs/api.log)"

echo "[wait] Waiting for API /healthz..."
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:${APP_PORT}/healthz" || true)
  if [[ "${code}" == "200" ]]; then
    echo "[ok] API ready"
    break
  fi
  if [[ "${i}" == "60" ]]; then
    echo "[ERR] API not ready after 60s" >&2
    tail -n 60 logs/api.log || true
    exit 1
  fi
  sleep 1
done

echo "[smoke] Running policy search smoke..."
bash scripts/smoke_api.sh "http://${HOST}:${APP_PORT}" "환불"

echo "[done] LLM+API up. PIDs: vLLM=${VLLM_PID}, API=${API_PID}"
