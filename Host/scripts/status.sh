#!/bin/bash
# status.sh - Check system health for the AI control system
#
# Run on: Proxmox Host

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

check_ok() {
    echo -e "  ${GREEN}[OK]${NC} $1"
}

check_warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
}

check_fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
}

check_service() {
    local service=$1
    if systemctl is-active --quiet "$service"; then
        check_ok "$service is running"
    else
        check_fail "$service is not running"
    fi
}

check_port() {
    local port=$1
    local desc=$2
    if ss -tlnp | grep -q ":$port "; then
        check_ok "$desc (port $port) is listening"
    else
        check_fail "$desc (port $port) is not listening"
    fi
}

check_device() {
    local device=$1
    local desc=$2
    if [[ -e "$device" ]]; then
        check_ok "$desc exists"
    else
        check_fail "$desc not found"
    fi
}

main() {
    echo ""
    echo "Proxmox Computer Control - System Status"
    echo "========================================="

    # Services
    print_header "Services"
    check_service "virtual-hid.service"
    check_service "input-router.service"

    if systemctl is-enabled vnc-bridge.service &>/dev/null; then
        check_service "vnc-bridge.service"
    else
        echo -e "  ${YELLOW}[SKIP]${NC} vnc-bridge.service (not enabled)"
    fi

    # Network
    print_header "Network"

    if ip link show vmbr1 &>/dev/null; then
        check_ok "Bridge vmbr1 exists"
        ip_addr=$(ip addr show vmbr1 | grep -oP 'inet \K[\d.]+')
        if [[ -n "$ip_addr" ]]; then
            check_ok "Bridge IP: $ip_addr"
        else
            check_warn "Bridge has no IP address"
        fi
    else
        check_fail "Bridge vmbr1 not found"
    fi

    # Ports
    print_header "Listening Ports"
    check_port 8888 "Mouse controller"
    check_port 8889 "Keyboard controller"

    # Devices
    print_header "Devices"
    check_device "/dev/uhid" "UHID device"
    check_device "/dev/uinput" "uinput device"

    # Check for virtual Logitech devices
    if ls /dev/input/by-id/ 2>/dev/null | grep -qi logitech; then
        check_ok "Virtual Logitech device found"
        ls /dev/input/by-id/ | grep -i logitech | while read dev; do
            echo "       $dev"
        done
    else
        check_warn "No virtual Logitech devices (may need USB passthrough)"
    fi

    # VMs
    print_header "Virtual Machines"
    if command -v qm &>/dev/null; then
        # Check Windows VM (100)
        if qm status 100 &>/dev/null; then
            vm_status=$(qm status 100 | grep -oP 'status: \K\w+')
            if [[ "$vm_status" == "running" ]]; then
                check_ok "Windows VM (100) is running"
            else
                check_warn "Windows VM (100) exists but status: $vm_status"
            fi
        else
            check_warn "Windows VM (100) not found"
        fi

        # Check Ubuntu VM (101)
        if qm status 101 &>/dev/null; then
            vm_status=$(qm status 101 | grep -oP 'status: \K\w+')
            if [[ "$vm_status" == "running" ]]; then
                check_ok "Ubuntu VM (101) is running"
            else
                check_warn "Ubuntu VM (101) exists but status: $vm_status"
            fi
        else
            check_warn "Ubuntu VM (101) not found"
        fi
    else
        check_warn "Proxmox qm command not available"
    fi

    # Connectivity
    print_header "Connectivity"

    # Ping Windows VM
    if ping -c 1 -W 1 192.168.100.100 &>/dev/null; then
        check_ok "Windows VM (192.168.100.100) is reachable"
    else
        check_warn "Windows VM (192.168.100.100) is not reachable"
    fi

    # Ping Ubuntu VM
    if ping -c 1 -W 1 192.168.100.101 &>/dev/null; then
        check_ok "Ubuntu VM (192.168.100.101) is reachable"
    else
        check_warn "Ubuntu VM (192.168.100.101) is not reachable"
    fi

    # Statistics
    print_header "Service Statistics"
    if systemctl is-active --quiet input-router.service; then
        echo "  Recent logs (last 5 lines):"
        journalctl -u input-router --no-pager -n 5 2>/dev/null | while read line; do
            echo "    $line"
        done
    fi

    # Summary
    print_header "Summary"
    echo "  Run on Proxmox host: $(hostname)"
    echo "  Time: $(date)"
    echo ""
    echo "  Management commands:"
    echo "    Start all:  /opt/proxmox-computer-control/host/scripts/start_all.sh"
    echo "    View logs:  journalctl -u input-router -f"
    echo "    Restart:    systemctl restart input-router"
    echo ""
}

main "$@"
