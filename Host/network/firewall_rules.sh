#!/bin/bash
# firewall_rules.sh - Configure firewall for VM-to-VM communication
#
# Sets up iptables rules to:
# - Allow traffic between VMs on the internal bridge (vmbr1)
# - Block external access to the internal network
# - Allow specific ports for HID controller and VNC
#
# Run on: Proxmox Host
# Requirements: Root privileges

set -e

INTERNAL_BRIDGE="vmbr1"
EXTERNAL_BRIDGE="vmbr0"
INTERNAL_NETWORK="192.168.100.0/24"
HOST_IP="192.168.100.1"
UBUNTU_VM_IP="192.168.100.100"
WINDOWS_VM_IP="192.168.100.101"

# HID Controller ports (on host)
MOUSE_PORT=8888
KEYBOARD_PORT=8889

# VNC port (on Windows VM)
VNC_PORT=5900

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

setup_base_rules() {
    log_info "Setting up base firewall rules..."

    # Flush existing rules for the internal bridge
    iptables -F FORWARD 2>/dev/null || true

    # Allow established connections
    iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
}

setup_isolation_rules() {
    log_info "Setting up network isolation rules..."

    # Block traffic from internal bridge to external bridge (prevent internet access)
    iptables -A FORWARD -i "$INTERNAL_BRIDGE" -o "$EXTERNAL_BRIDGE" -j DROP
    iptables -A FORWARD -i "$EXTERNAL_BRIDGE" -o "$INTERNAL_BRIDGE" -j DROP

    # Block traffic from internal network to host's external interface
    iptables -A INPUT -i "$INTERNAL_BRIDGE" ! -s "$INTERNAL_NETWORK" -j DROP

    log_info "Internal network isolated from external network"
}

setup_inter_vm_rules() {
    log_info "Setting up inter-VM communication rules..."

    # Allow all traffic between VMs on the internal bridge
    iptables -A FORWARD -i "$INTERNAL_BRIDGE" -o "$INTERNAL_BRIDGE" -j ACCEPT

    # Allow Ubuntu VM to connect to HID controller on host
    iptables -A INPUT -i "$INTERNAL_BRIDGE" -s "$UBUNTU_VM_IP" -p tcp --dport "$MOUSE_PORT" -j ACCEPT
    iptables -A INPUT -i "$INTERNAL_BRIDGE" -s "$UBUNTU_VM_IP" -p tcp --dport "$KEYBOARD_PORT" -j ACCEPT

    # Allow Ubuntu VM to connect to Windows VM VNC
    iptables -A FORWARD -i "$INTERNAL_BRIDGE" -s "$UBUNTU_VM_IP" -d "$WINDOWS_VM_IP" -p tcp --dport "$VNC_PORT" -j ACCEPT

    log_info "Inter-VM communication enabled"
}

setup_security_rules() {
    log_info "Setting up security rules..."

    # Drop all other traffic to HID controller ports from non-Ubuntu sources
    iptables -A INPUT -i "$INTERNAL_BRIDGE" -p tcp --dport "$MOUSE_PORT" -j DROP
    iptables -A INPUT -i "$INTERNAL_BRIDGE" -p tcp --dport "$KEYBOARD_PORT" -j DROP

    # Rate limit new connections (anti-DoS)
    iptables -A INPUT -i "$INTERNAL_BRIDGE" -p tcp --syn -m limit --limit 10/s --limit-burst 20 -j ACCEPT

    # Log dropped packets (for debugging)
    iptables -A INPUT -i "$INTERNAL_BRIDGE" -j LOG --log-prefix "vmbr1-dropped: " --log-level 4

    log_info "Security rules applied"
}

save_rules() {
    log_info "Saving firewall rules..."

    # Save for Debian/Ubuntu
    if command -v iptables-save &>/dev/null; then
        iptables-save > /etc/iptables.rules

        # Create restore script
        cat > /etc/network/if-pre-up.d/iptables << 'EOF'
#!/bin/bash
/sbin/iptables-restore < /etc/iptables.rules
EOF
        chmod +x /etc/network/if-pre-up.d/iptables

        log_info "Rules saved to /etc/iptables.rules"
    fi

    # Also save to Proxmox firewall format if available
    if [[ -d /etc/pve/firewall ]]; then
        cat > /etc/pve/firewall/cluster.fw << EOF
[OPTIONS]
enable: 1
policy_in: DROP
policy_out: ACCEPT

[RULES]
# Allow SSH
IN ACCEPT -p tcp -dport 22

# Allow Proxmox web interface
IN ACCEPT -p tcp -dport 8006

# Allow HID controller from Ubuntu VM
IN ACCEPT -source $UBUNTU_VM_IP -p tcp -dport $MOUSE_PORT
IN ACCEPT -source $UBUNTU_VM_IP -p tcp -dport $KEYBOARD_PORT

[IPSET vm_internal]
$WINDOWS_VM_IP
$UBUNTU_VM_IP
EOF
        log_info "Proxmox firewall configured"
    fi
}

show_status() {
    echo ""
    log_info "Current iptables rules:"
    echo ""
    iptables -L -n -v --line-numbers
    echo ""
    log_info "NAT rules:"
    iptables -t nat -L -n -v --line-numbers
}

flush_rules() {
    log_warn "Flushing all firewall rules..."
    iptables -F
    iptables -X
    iptables -t nat -F
    iptables -t nat -X
    iptables -P INPUT ACCEPT
    iptables -P FORWARD ACCEPT
    iptables -P OUTPUT ACCEPT
    log_info "All rules flushed"
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup     Configure all firewall rules"
    echo "  status    Show current firewall rules"
    echo "  flush     Remove all firewall rules"
    echo "  save      Save current rules to disk"
    echo ""
}

case "${1:-setup}" in
    setup)
        check_root
        setup_base_rules
        setup_isolation_rules
        setup_inter_vm_rules
        setup_security_rules
        save_rules
        log_info "Firewall setup complete!"
        echo ""
        echo "Summary:"
        echo "  - Internal network ($INTERNAL_NETWORK) isolated from external"
        echo "  - Ubuntu VM ($UBUNTU_VM_IP) can access HID controller ports"
        echo "  - Ubuntu VM can access Windows VM VNC on port $VNC_PORT"
        echo "  - All other external access blocked"
        ;;
    status)
        show_status
        ;;
    flush)
        check_root
        flush_rules
        ;;
    save)
        check_root
        save_rules
        ;;
    *)
        usage
        exit 1
        ;;
esac
