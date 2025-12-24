#!/usr/bin/env bash
set -euo pipefail

# OpenAI 호환 레이어 전체 테스트
# Usage:
#   bash scripts/test_oai_compat.sh [BASE_URL]
# Defaults:
#   BASE_URL=http://localhost:8000

BASE_URL="${1:-http://localhost:8000}"

echo "=========================================="
echo " OpenAI 호환 레이어 테스트"
echo " Target: ${BASE_URL}"
echo "=========================================="

# 1. 헬스체크
echo ""
echo "=== 1. 헬스체크 ==="
health=$(curl -s "${BASE_URL}/healthz" || echo '{"status":"error"}')
echo "${health}"

# 2. /v1/models
echo ""
echo "=== 2. /v1/models ==="
models_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/models" || true)
if [ "${models_code}" = "200" ]; then
  echo "[OK] /v1/models (200)"
  curl -s "${BASE_URL}/v1/models" | python3 -m json.tool 2>/dev/null || curl -s "${BASE_URL}/v1/models"
elif [ "${models_code}" = "404" ]; then
  echo "[SKIP] /v1/models disabled (openai_compat.enabled=false)"
else
  echo "[ERROR] /v1/models returned HTTP ${models_code}"
fi

# 3. /v1/chat/completions (비스트리밍)
echo ""
echo "=== 3. /v1/chat/completions (비스트리밍) ==="
chat_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"환불 정책 알려줘"}]}' || true)
if [ "${chat_code}" = "200" ]; then
  echo "[OK] /v1/chat/completions (200)"
  curl -s -X POST "${BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"환불 정책 알려줘"}]}' | python3 -m json.tool 2>/dev/null || \
  curl -s -X POST "${BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"환불 정책 알려줘"}]}'
elif [ "${chat_code}" = "404" ]; then
  echo "[SKIP] /v1/chat/completions disabled (openai_compat.enabled=false)"
else
  echo "[ERROR] /v1/chat/completions returned HTTP ${chat_code}"
fi

# 4. /v1/chat/completions (스트리밍)
echo ""
echo "=== 4. /v1/chat/completions (스트리밍) ==="
if [ "${chat_code}" = "200" ]; then
  echo "[OK] 스트리밍 테스트 시작..."
  curl -s -N -X POST "${BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"배송 정책"}],"stream":true}' | head -20
  echo ""
  echo "[OK] 스트리밍 완료"
else
  echo "[SKIP] 스트리밍 테스트 스킵 (chat endpoint 미활성화)"
fi

# 5. 정책 검색 (기본 API)
echo ""
echo "=== 5. 정책 검색 (기본 API) ==="
search_code=$(curl -s -o /dev/null -w "%{http_code}" --get "${BASE_URL}/policies/search" \
  --data-urlencode "q=환불" --data-urlencode "top_k=3" || true)
if [ "${search_code}" = "200" ]; then
  echo "[OK] /policies/search (200)"
  curl -s --get "${BASE_URL}/policies/search" \
    --data-urlencode "q=환불" --data-urlencode "top_k=3" | python3 -m json.tool 2>/dev/null | head -30 || \
  curl -s --get "${BASE_URL}/policies/search" \
    --data-urlencode "q=환불" --data-urlencode "top_k=3" | head -500
else
  echo "[ERROR] /policies/search returned HTTP ${search_code}"
fi

# 6. 주문 조회 테스트
echo ""
echo "=== 6. /v1/chat/completions (주문 조회) ==="
if [ "${chat_code}" = "200" ]; then
  curl -s -X POST "${BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"주문 ORD001 상태 알려줘"}]}' | python3 -m json.tool 2>/dev/null || \
  curl -s -X POST "${BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"ecommerce-agent-merged","messages":[{"role":"user","content":"주문 ORD001 상태 알려줘"}]}'
else
  echo "[SKIP]"
fi

echo ""
echo "=========================================="
echo " 테스트 완료"
echo "=========================================="
