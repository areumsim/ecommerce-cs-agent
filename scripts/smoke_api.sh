#!/usr/bin/env bash
set -euo pipefail

# Simple API smoke check
# Usage:
#   bash scripts/smoke_api.sh [BASE_URL] [QUERY]
# Defaults:
#   BASE_URL=http://localhost:8000
#   QUERY=환불

BASE_URL="${1:-http://localhost:8000}"
QUERY="${2:-환불}"

echo "[smoke] Target: ${BASE_URL}"

# Wait for API to be ready (healthz)
max_retries=30
for i in $(seq 1 ${max_retries}); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/healthz" || true)
  if [ "${code}" = "200" ]; then
    echo "[smoke] Healthz OK (200) on attempt ${i}"
    break
  fi
  if [ "${i}" = "${max_retries}" ]; then
    echo "[smoke] Healthz failed after ${max_retries} attempts (last code: ${code})" >&2
    exit 1
  fi
  sleep 1
done

# Check policy search endpoint
search_code=$(curl -s -o /dev/null -w "%{http_code}" --get "${BASE_URL}/policies/search" \
  --data-urlencode "q=${QUERY}" --data-urlencode "top_k=3" || true)

if [ "${search_code}" != "200" ]; then
  echo "[smoke] Search endpoint returned HTTP ${search_code}" >&2
  exit 1
fi

echo "[smoke] Search OK (200). Sample response:"
curl -s --get "${BASE_URL}/policies/search" \
  --data-urlencode "q=${QUERY}" --data-urlencode "top_k=3" | sed -e 's/\n/ /g' | head -c 500; echo

# Check OAI-compatible /v1/models endpoint
echo ""
echo "[smoke] Checking OAI-compatible /v1/models..."
models_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/models" || true)
if [ "${models_code}" = "200" ]; then
  echo "[smoke] /v1/models OK (200)"
  curl -s "${BASE_URL}/v1/models" | head -c 300; echo
elif [ "${models_code}" = "404" ]; then
  echo "[smoke] /v1/models disabled (openai_compat.enabled=false)"
else
  echo "[smoke] /v1/models returned HTTP ${models_code}" >&2
fi

# Check OAI-compatible /v1/chat/completions endpoint
echo ""
echo "[smoke] Checking OAI-compatible /v1/chat/completions..."
chat_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"환불 정책 알려줘"}]}' || true)
if [ "${chat_code}" = "200" ]; then
  echo "[smoke] /v1/chat/completions OK (200)"
  curl -s -X POST "${BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"환불 정책 알려줘"}]}' | head -c 500; echo
elif [ "${chat_code}" = "404" ]; then
  echo "[smoke] /v1/chat/completions disabled (openai_compat.enabled=false)"
else
  echo "[smoke] /v1/chat/completions returned HTTP ${chat_code}" >&2
fi

echo ""
echo "[smoke] Done."
