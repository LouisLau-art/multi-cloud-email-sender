#!/bin/bash

# Usage:
#   ./start.sh       Foreground mode: show logs in terminal + persist to ./logs/*.log
#   ./start.sh -d    Daemon mode: run in background, logs persisted to ./logs/*.log
#   ./start.sh -k    Force-kill listeners on ports 8000/5173 before start
#   ./start.sh -s    Stop listeners on ports 8000/5173 and exit

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
STARTUP_TIMEOUT_SECONDS=8
BACKEND_PYTHON=""

DAEMON_MODE=false
FORCE_KILL=false
STOP_ONLY=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        -d)
            DAEMON_MODE=true
            ;;
        -k)
            FORCE_KILL=true
            ;;
        -s)
            STOP_ONLY=true
            ;;
        *)
            echo "[ERROR] Unknown option: $1"
            echo "Usage: ./start.sh [-d] [-k] [-s]"
            echo "  -d  Start in daemon mode (do not follow logs)"
            echo "  -k  Force-kill listeners on 8000/5173 before start"
            echo "  -s  Stop listeners on 8000/5173 and exit"
            exit 1
            ;;
    esac
    shift
done

mkdir -p "$LOG_DIR"
touch "$BACKEND_LOG" "$FRONTEND_LOG"

run_line_buffered() {
    if command -v stdbuf >/dev/null 2>&1; then
        stdbuf -oL -eL "$@"
    else
        "$@"
    fi
}

resolve_backend_python() {
    if [ -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
        BACKEND_PYTHON="$ROOT_DIR/backend/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        BACKEND_PYTHON="$(command -v python3)"
    else
        echo "[ERROR] python3 not found."
        return 1
    fi
    return 0
}

check_backend_runtime() {
    "$BACKEND_PYTHON" - <<'PY' >/dev/null 2>&1
import uvicorn
raise SystemExit(0 if hasattr(uvicorn, "run") else 1)
PY
    if [ $? -ne 0 ]; then
        echo "[ERROR] Backend runtime check failed: uvicorn is not usable in $BACKEND_PYTHON"
        echo "[HINT] Recommended fix:"
        echo "  python3 -m venv backend/.venv"
        echo "  backend/.venv/bin/pip install -r backend/requirements.txt"
        echo "Then rerun: ./start.sh"
        return 1
    fi
    return 0
}

stop_existing() {
    for spec in "backend:$BACKEND_PID_FILE" "frontend:$FRONTEND_PID_FILE"; do
        local name="${spec%%:*}"
        local pid_file="${spec##*:}"
        if [ ! -f "$pid_file" ]; then
            continue
        fi

        local pid
        pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [ -z "$pid" ]; then
            continue
        fi

        if kill -0 "$pid" >/dev/null 2>&1; then
            local cmdline
            cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
            if [ "$name" = "backend" ] && [[ "$cmdline" != *"uvicorn app.main:app"* ]]; then
                continue
            fi
            if [ "$name" = "frontend" ] && [[ "$cmdline" != *"vite --host"* ]]; then
                continue
            fi
            echo "Stopping previous $name process: PID $pid"
            kill "$pid" >/dev/null 2>&1 || true
            sleep 1
        fi
    done
}

start_backend_foreground() {
    (
        cd "$ROOT_DIR/backend" || exit 1
        PYTHONUNBUFFERED=1 run_line_buffered "$BACKEND_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 \
            | awk '{ print strftime("[%Y-%m-%d %H:%M:%S]"), "[backend]", $0; fflush(); }' \
            | tee -a "$BACKEND_LOG"
    ) &
    BACKEND_PID=$!
}

start_frontend_foreground() {
    (
        cd "$ROOT_DIR/frontend" || exit 1
        run_line_buffered npm run dev -- --host 2>&1 \
            | awk '{ print strftime("[%Y-%m-%d %H:%M:%S]"), "[frontend]", $0; fflush(); }' \
            | tee -a "$FRONTEND_LOG"
    ) &
    FRONTEND_PID=$!
}

start_backend_daemon() {
    nohup bash -lc "cd '$ROOT_DIR/backend' && if command -v stdbuf >/dev/null 2>&1; then PYTHONUNBUFFERED=1 stdbuf -oL -eL '$BACKEND_PYTHON' -m uvicorn app.main:app --host 0.0.0.0 --port 8000; else PYTHONUNBUFFERED=1 '$BACKEND_PYTHON' -m uvicorn app.main:app --host 0.0.0.0 --port 8000; fi 2>&1 | awk '{ print strftime(\"[%Y-%m-%d %H:%M:%S]\"), \"[backend]\", \$0; fflush(); }' >> '$BACKEND_LOG'" >/dev/null 2>&1 &
    BACKEND_PID=$!
}

start_frontend_daemon() {
    nohup bash -lc "cd '$ROOT_DIR/frontend' && if command -v stdbuf >/dev/null 2>&1; then stdbuf -oL -eL npm run dev -- --host; else npm run dev -- --host; fi 2>&1 | awk '{ print strftime(\"[%Y-%m-%d %H:%M:%S]\"), \"[frontend]\", \$0; fflush(); }' >> '$FRONTEND_LOG'" >/dev/null 2>&1 &
    FRONTEND_PID=$!
}

cleanup_foreground() {
    kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
    wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}

cleanup_daemon() {
    kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}

get_port_listener_pids() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u
        return 0
    fi

    ss -ltnp 2>/dev/null \
        | awk -v p="$port" '$4 ~ (":" p "$") {print $NF}' \
        | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' \
        | sort -u
}

kill_port_listeners() {
    local port="$1"
    local pids
    pids="$(get_port_listener_pids "$port")"
    if [ -z "$pids" ]; then
        return 0
    fi

    while read -r pid; do
        [ -z "$pid" ] && continue
        echo "[WARN] Killing PID $pid on port $port"
        kill "$pid" >/dev/null 2>&1 || true
        sleep 1
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill -9 "$pid" >/dev/null 2>&1 || true
        fi
    done <<< "$pids"
}

is_port_listening() {
    local port="$1"
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
}

wait_for_service() {
    local name="$1"
    local port="$2"
    local log_file="$3"
    local i=0
    while [ "$i" -lt "$STARTUP_TIMEOUT_SECONDS" ]; do
        if is_port_listening "$port"; then
            return 0
        fi
        sleep 1
        i=$((i + 1))
    done
    echo "[ERROR] $name failed to start on port $port."
    echo "[ERROR] Recent $name logs ($log_file):"
    tail -n 120 "$log_file" || true
    return 1
}

print_frontend_network_info() {
    local ips=""
    if command -v hostname >/dev/null 2>&1; then
        ips="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | sort -u || true)"
    fi

    if [ -z "$ips" ] && command -v ip >/dev/null 2>&1; then
        ips="$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | sort -u || true)"
    fi

    if [ -n "$ips" ]; then
        while read -r ip; do
            [ -z "$ip" ] && continue
            local line="[frontend]   -> Network: http://$ip:5173/"
            echo "$line"
            printf "%s %s\n" "$(date '+[%Y-%m-%d %H:%M:%S]')" "$line" >> "$FRONTEND_LOG"
        done <<< "$ips"
    else
        local line="[frontend]   -> Network: unavailable (no non-loopback IPv4 detected)"
        echo "$line"
        printf "%s %s\n" "$(date '+[%Y-%m-%d %H:%M:%S]')" "$line" >> "$FRONTEND_LOG"
    fi
}

echo "Stopping existing managed services..."
stop_existing

if [ "$STOP_ONLY" = true ]; then
    echo "Stopping listeners on ports 8000/5173..."
    kill_port_listeners 8000
    kill_port_listeners 5173
    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
    echo "Done."
    exit 0
fi

if ! resolve_backend_python; then
    exit 1
fi
echo "Backend Python: $BACKEND_PYTHON"
if ! check_backend_runtime; then
    exit 1
fi

if [ "$FORCE_KILL" = true ]; then
    echo "[WARN] Force-killing listeners on 8000/5173..."
    kill_port_listeners 8000
    kill_port_listeners 5173
fi

if is_port_listening 8000; then
    echo "[ERROR] Port 8000 is already in use by another process. Refusing to force kill."
    ss -ltnp | grep ':8000' || true
    exit 1
fi
if is_port_listening 5173; then
    echo "[ERROR] Port 5173 is already in use by another process. Refusing to force kill."
    ss -ltnp | grep ':5173' || true
    exit 1
fi

echo "Starting Backend..."
if [ "$DAEMON_MODE" = true ]; then
    start_backend_daemon
else
    start_backend_foreground
fi
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

if ! wait_for_service "Backend" 8000 "$BACKEND_LOG"; then
    if [ "$DAEMON_MODE" = true ]; then
        cleanup_daemon
    else
        cleanup_foreground
    fi
    exit 1
fi

echo "Starting Frontend..."
if [ "$DAEMON_MODE" = true ]; then
    start_frontend_daemon
else
    start_frontend_foreground
fi
echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

if ! wait_for_service "Frontend" 5173 "$FRONTEND_LOG"; then
    if [ "$DAEMON_MODE" = true ]; then
        cleanup_daemon
    else
        cleanup_foreground
    fi
    exit 1
fi

echo "App running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
print_frontend_network_info
echo "Logs:"
echo "  $BACKEND_LOG"
echo "  $FRONTEND_LOG"

if [ "$DAEMON_MODE" = true ]; then
    echo "Daemon mode enabled."
    echo "PIDs:"
    echo "  Backend:  $BACKEND_PID (saved in $BACKEND_PID_FILE)"
    echo "  Frontend: $FRONTEND_PID (saved in $FRONTEND_PID_FILE)"
    echo "Follow logs:"
    echo "  tail -f $BACKEND_LOG"
    echo "  tail -f $FRONTEND_LOG"
    echo "Stop:"
    echo "  ./start.sh -s"
else
    echo "Foreground mode: logs are shown in terminal and persisted to files."
    echo "Press Ctrl+C to stop."
    trap cleanup_foreground EXIT INT TERM
    wait
fi
