#!/bin/bash
# vmbr1_config.sh - Configure internal VM bridge for inter-VM communication
#
# Creates a private bridge network (192.168.100.0/24) isolated from external access.
# This bridge is used for communication between the Ubuntu AI Controller and Windows VM.
#
# Run on: Proxmox Host
# Requirements: Root privileges

set -e

BRIDGE_NAME="vmbr1"
BRIDGE_IP="192.168.100.1"
BRIDGE_NETMASK="24"
NETWORK="192.168.100.0/24"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

check_bridge_exists() {
    if ip link show "$BRIDGE_NAME" &>/dev/null; then
        return 0
    fi
    return 1
}

create_bridge() {
    log_info "Creating bridge $BRIDGE_NAME..."

    # Check if already exists
    if check_bridge_exists; then
        log_warn "Bridge $BRIDGE_NAME already exists"
        return 0
    fi

    # Create the bridge
    ip link add name "$BRIDGE_NAME" type bridge
    ip link set "$BRIDGE_NAME" up
    ip addr add "${BRIDGE_IP}/${BRIDGE_NETMASK}" dev "$BRIDGE_NAME"

    log_info "Bridge $BRIDGE_NAME created with IP ${BRIDGE_IP}/${BRIDGE_NETMASK}"
}

configure_interfaces_file() {
    INTERFACES_FILE="/etc/network/interfaces"
    BACKUP_FILE="/etc/network/interfaces.backup.$(date +%Y%m%d_%H%M%S)"

    log_info "Configuring $INTERFACES_FILE..."

    # Check if already configured
    if grep -q "iface $BRIDGE_NAME" "$INTERFACES_FILE"; then
        log_warn "Bridge $BRIDGE_NAME already configured in $INTERFACES_FILE"
        return 0
    fi

    # Backup existing file
    cp "$INTERFACES_FILE" "$BACKUP_FILE"
    log_info "Backed up to $BACKUP_FILE"

    # Append bridge configuration
    cat >> "$INTERFACES_FILE" << EOF

# Internal bridge for VM-to-VM communication
# Created by vmbr1_config.sh
auto $BRIDGE_NAME
iface $BRIDGE_NAME inet static
    address $BRIDGE_IP/$BRIDGE_NETMASK
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    # Prevent external routing
    post-up iptables -I FORWARD -i $BRIDGE_NAME -o vmbr0 -j DROP
    post-up iptables -I FORWARD -i vmbr0 -o $BRIDGE_NAME -j DROP
EOF

    log_info "Bridge configuration added to $INTERFACES_FILE"
}

configure_sysctl() {
    log_info "Configuring kernel parameters..."

    SYSCTL_CONF="/etc/sysctl.d/99-vm-bridge.conf"

    cat > "$SYSCTL_CONF" << EOF
# VM Bridge configuration
# Enable IP forwarding for VM communication
net.ipv4.ip_forward = 1

# Disable bridge netfilter (for performance)
net.bridge.bridge-nf-call-iptables = 0
net.bridge.bridge-nf-call-ip6tables = 0
net.bridge.bridge-nf-call-arptables = 0
EOF

    sysctl -p "$SYSCTL_CONF"
    log_info "Kernel parameters configured"
}

show_status() {
    echo ""
    log_info "Bridge Status:"
    ip addr show "$BRIDGE_NAME" 2>/dev/null || log_warn "Bridge not found"
    echo ""
    log_info "Bridge Link:"
    ip link show "$BRIDGE_NAME" 2>/dev/null || log_warn "Bridge not found"
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup     Create and configure the internal bridge"
    echo "  status    Show bridge status"
    echo "  remove    Remove the bridge (requires reboot to fully apply)"
    echo ""
}

case "${1:-setup}" in
    setup)
        check_root
        create_bridge
        configure_interfaces_file
        configure_sysctl
        show_status
        log_info "Bridge setup complete!"
        echo ""
        echo "Next steps:"
        echo "  1. Add to Windows VM (ID 100): qm set 100 --net1 virtio,bridge=$BRIDGE_NAME"
        echo "  2. Add to Ubuntu VM (ID 101): qm set 101 --net1 virtio,bridge=$BRIDGE_NAME"
        echo "  3. Configure static IPs inside VMs:"
        echo "     - Windows: 192.168.100.100"
        echo "     - Ubuntu:  192.168.100.101"
        ;;
    status)
        show_status
        ;;
    remove)
        check_root
        log_info "Removing bridge $BRIDGE_NAME..."
        ip link set "$BRIDGE_NAME" down 2>/dev/null || true
        ip link delete "$BRIDGE_NAME" 2>/dev/null || true
        log_warn "Bridge removed. Edit /etc/network/interfaces to remove configuration."
        log_warn "A reboot may be required for full cleanup."
        ;;
    *)
        usage
        exit 1
        ;;
esac
