#!/bin/bash
# 시각화 데이터 주기적 업데이트 스크립트
#
# crontab 등록 예시 (매 시간):
#   0 * * * * /path/to/ecommerce-cs-agent/scripts/update_visualization_cron.sh
#
# 또는 systemd timer, supervisor 등으로 관리

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/visualization_update.log"

mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "시각화 데이터 업데이트 시작"

cd "$PROJECT_DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

$PYTHON scripts/export_visualization_data.py --sample-size 50 >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log "업데이트 완료"
else
    log "업데이트 실패"
    exit 1
fi
