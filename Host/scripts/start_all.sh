#!/bin/bash
# start_all.sh - Start all host services for the AI control system
#
# Run on: Proxmox Host
# Requirements: Services must be installed (run install.sh first)

set -e

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

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

start_service() {
    local service=$1
    local required=${2:-true}

    if systemctl is-active --quiet "$service"; then
        log_info "$service is already running"
    else
        log_info "Starting $service..."
        if systemctl start "$service"; then
            log_info "$service started successfully"
        else
            if [[ "$required" == "true" ]]; then
                log_error "Failed to start $service"
                return 1
            else
                log_warn "Failed to start $service (optional)"
            fi
        fi
    fi
}

verify_network() {
    log_info "Verifying network bridge..."

    if ip link show vmbr1 &>/dev/null; then
        log_info "Bridge vmbr1 is up"
        ip addr show vmbr1 | grep inet
    else
        log_error "Bridge vmbr1 not found. Run network/vmbr1_config.sh setup"
        return 1
    fi
}

verify_ports() {
    log_info "Verifying listening ports..."

    sleep 2  # Give services time to start

    for port in 8888 8889; do
        if ss -tlnp | grep -q ":$port "; then
            log_info "Port $port is listening"
        else
            log_warn "Port $port is not listening"
        fi
    done
}

main() {
    check_root

    echo "Starting Proxmox Computer Control - Host Services"
    echo "=================================================="
    echo ""

    # Verify network is ready
    verify_network

    # Start services in order
    echo ""
    log_info "Starting services..."

    # Virtual HID creation (dependency)
    start_service "virtual-hid.service" true

    # HID controller (main service)
    start_service "input-router.service" true

    # VNC bridge (optional)
    if systemctl is-enabled vnc-bridge.service &>/dev/null; then
        start_service "vnc-bridge.service" false
    fi

    # Verify
    echo ""
    verify_ports

    echo ""
    log_info "All services started!"
    echo ""
    echo "Monitor logs with:"
    echo "  journalctl -u input-router -f"
    echo ""
    echo "Test mouse with:"
    echo "  echo '{\"type\":\"mouse_move\",\"x\":10,\"y\":0}' | nc localhost 8888"
    echo ""
    echo "Test keyboard with:"
    echo "  echo '{\"type\":\"keyboard\",\"key\":\"a\",\"action\":\"press\"}' | nc localhost 8889"
}

main "$@"
