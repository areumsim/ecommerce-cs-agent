#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
UI_PID_FILE="$PROJECT_DIR/.ui.pid"
API_PID_FILE="$PROJECT_DIR/.api.pid"
UI_LOG="$PROJECT_DIR/.ui.log"
API_LOG="$PROJECT_DIR/.api.log"
UI_PORT="${UI_PORT:-7860}"
API_PORT="${API_PORT:-8000}"

check_port() {
    local port=$1
    curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" --connect-timeout 2 2>/dev/null | grep -q "200\|404\|302" && return 0 || return 1
}

wait_for_port() {
    local port=$1
    local max_wait=$2
    local count=0
    while [ $count -lt $max_wait ]; do
        if check_port "$port"; then
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    return 1
}

kill_by_pid_file() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file" 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill -TERM "$pid" 2>/dev/null || true
            sleep 1
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pid_file"
    fi
}

kill_by_pattern() {
    local pattern=$1
    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs -r kill -TERM 2>/dev/null || true
        sleep 1
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        [ -n "$pids" ] && echo "$pids" | xargs -r kill -9 2>/dev/null || true
    fi
}

stop_ui() {
    echo "[INFO] Stopping UI server..."
    kill_by_pid_file "$UI_PID_FILE"
    kill_by_pattern "python.*ui\.py"
    echo "[OK] UI stopped"
}

stop_api() {
    echo "[INFO] Stopping API server..."
    kill_by_pid_file "$API_PID_FILE"
    kill_by_pattern "uvicorn.*api:app"
    echo "[OK] API stopped"
}

stop_all() {
    stop_ui
    stop_api
}

start_ui() {
    echo "[INFO] Starting UI server on port $UI_PORT..."
    stop_ui
    
    cd "$PROJECT_DIR"
    nohup python ui.py > "$UI_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$UI_PID_FILE"
    
    echo "[INFO] Waiting for UI (PID: $pid)..."
    if wait_for_port "$UI_PORT" 60; then
        echo "[OK] UI server started: http://localhost:$UI_PORT"
    else
        echo "[ERROR] UI failed to start. Log:"
        tail -20 "$UI_LOG" 2>/dev/null || true
        return 1
    fi
}

start_api() {
    echo "[INFO] Starting API server on port $API_PORT..."
    stop_api
    
    cd "$PROJECT_DIR"
    nohup uvicorn api:app --host 0.0.0.0 --port "$API_PORT" > "$API_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$API_PID_FILE"
    
    echo "[INFO] Waiting for API (PID: $pid)..."
    if wait_for_port "$API_PORT" 30; then
        echo "[OK] API server started: http://localhost:$API_PORT"
    else
        echo "[ERROR] API failed to start. Log:"
        tail -20 "$API_LOG" 2>/dev/null || true
        return 1
    fi
}

start_all() {
    start_api
    start_ui
}

status() {
    echo "=== Service Status ==="
    
    if [ -f "$UI_PID_FILE" ] && ps -p "$(cat "$UI_PID_FILE" 2>/dev/null)" > /dev/null 2>&1; then
        echo "[UI]  Running (PID: $(cat "$UI_PID_FILE"))"
    else
        echo "[UI]  Stopped"
    fi
    
    if check_port "$UI_PORT"; then
        echo "      Port $UI_PORT: LISTENING"
    else
        echo "      Port $UI_PORT: NOT LISTENING"
    fi
    
    if [ -f "$API_PID_FILE" ] && ps -p "$(cat "$API_PID_FILE" 2>/dev/null)" > /dev/null 2>&1; then
        echo "[API] Running (PID: $(cat "$API_PID_FILE"))"
    else
        echo "[API] Stopped"
    fi
    
    if check_port "$API_PORT"; then
        echo "      Port $API_PORT: LISTENING"
    else
        echo "      Port $API_PORT: NOT LISTENING"
    fi
}

logs_ui() {
    [ -f "$UI_LOG" ] && tail -f "$UI_LOG" || echo "[ERROR] No UI log file"
}

logs_api() {
    [ -f "$API_LOG" ] && tail -f "$API_LOG" || echo "[ERROR] No API log file"
}

case "${1:-}" in
    start)
        case "${2:-all}" in
            ui) start_ui ;;
            api) start_api ;;
            all|"") start_all ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    stop)
        case "${2:-all}" in
            ui) stop_ui ;;
            api) stop_api ;;
            all|"") stop_all ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    restart)
        case "${2:-all}" in
            ui) stop_ui; start_ui ;;
            api) stop_api; start_api ;;
            all|"") stop_all; start_all ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    status)
        status
        ;;
    logs)
        case "${2:-}" in
            ui) logs_ui ;;
            api) logs_api ;;
            *) echo "Usage: $0 logs {ui|api}"; exit 1 ;;
        esac
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs} [ui|api|all]"
        echo ""
        echo "Commands:"
        echo "  start [service]   - Start services (default: all)"
        echo "  stop [service]    - Stop services (default: all)"
        echo "  restart [service] - Restart services (default: all)"
        echo "  status            - Show service status"
        echo "  logs {ui|api}     - Tail log file"
        echo ""
        echo "Services: ui, api, all"
        echo ""
        echo "Ports: UI=$UI_PORT, API=$API_PORT"
        exit 1
        ;;
esac
