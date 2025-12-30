#!/bin/bash
# start_agent.sh - Start the AI agent
#
# Run on: Ubuntu AI Controller VM
# Requirements: Python environment set up, models installed

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$BASE_DIR/venv"
LOG_DIR="$BASE_DIR/logs"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Python virtual environment
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    # Check dependencies
    if ! python -c "import cv2" 2>/dev/null; then
        log_warn "Installing dependencies..."
        pip install -r "$BASE_DIR/requirements.txt"
    fi

    # Check Ollama
    if ! pgrep -x "ollama" > /dev/null; then
        log_info "Starting Ollama..."
        ollama serve &
        sleep 3
    fi

    # Create logs directory
    mkdir -p "$LOG_DIR"
}

check_connections() {
    log_info "Checking connections..."

    # Check HID controller
    if nc -z 192.168.100.1 8888 2>/dev/null; then
        log_info "HID controller (mouse): OK"
    else
        log_warn "HID controller (mouse): NOT REACHABLE"
    fi

    if nc -z 192.168.100.1 8889 2>/dev/null; then
        log_info "HID controller (keyboard): OK"
    else
        log_warn "HID controller (keyboard): NOT REACHABLE"
    fi

    # Check Windows VM VNC
    if nc -z 192.168.100.100 5900 2>/dev/null; then
        log_info "Windows VM VNC: OK"
    else
        log_warn "Windows VM VNC: NOT REACHABLE"
    fi
}

start_agent() {
    log_info "Starting AI agent..."

    cd "$BASE_DIR"
    source "$VENV_DIR/bin/activate"

    # Set PYTHONPATH
    export PYTHONPATH="$BASE_DIR/src:$PYTHONPATH"

    # Run agent
    python -m src.agent.main_agent --config config/config.yaml "$@"
}

start_background() {
    log_info "Starting agent in background..."

    cd "$BASE_DIR"
    source "$VENV_DIR/bin/activate"
    export PYTHONPATH="$BASE_DIR/src:$PYTHONPATH"

    nohup python -m src.agent.main_agent --config config/config.yaml \
        > "$LOG_DIR/agent.log" 2>&1 &

    echo $! > "$LOG_DIR/agent.pid"
    log_info "Agent started with PID $(cat $LOG_DIR/agent.pid)"
    log_info "Logs: $LOG_DIR/agent.log"
}

stop_agent() {
    if [[ -f "$LOG_DIR/agent.pid" ]]; then
        PID=$(cat "$LOG_DIR/agent.pid")
        if kill -0 "$PID" 2>/dev/null; then
            log_info "Stopping agent (PID $PID)..."
            kill "$PID"
            rm "$LOG_DIR/agent.pid"
        else
            log_warn "Agent not running"
            rm "$LOG_DIR/agent.pid"
        fi
    else
        log_warn "No PID file found"
    fi
}

status() {
    if [[ -f "$LOG_DIR/agent.pid" ]]; then
        PID=$(cat "$LOG_DIR/agent.pid")
        if kill -0 "$PID" 2>/dev/null; then
            log_info "Agent running (PID $PID)"
            echo ""
            echo "Recent logs:"
            tail -10 "$LOG_DIR/agent.log" 2>/dev/null || echo "(no logs)"
        else
            log_warn "Agent not running (stale PID file)"
        fi
    else
        log_warn "Agent not running"
    fi
}

usage() {
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  start      Start agent in foreground (default)"
    echo "  background Start agent in background"
    echo "  stop       Stop background agent"
    echo "  status     Check agent status"
    echo "  check      Check prerequisites and connections"
    echo ""
    echo "Options are passed to the agent."
}

case "${1:-start}" in
    start)
        shift || true
        check_prerequisites
        check_connections
        start_agent "$@"
        ;;
    background)
        check_prerequisites
        check_connections
        start_background
        ;;
    stop)
        stop_agent
        ;;
    status)
        status
        ;;
    check)
        check_prerequisites
        check_connections
        ;;
    *)
        usage
        exit 1
        ;;
esac
