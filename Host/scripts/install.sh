#!/bin/bash
# install.sh - Full installation script for Proxmox Host components
#
# This script sets up all host-side components for the AI computer control system:
# - Virtual HID device creation
# - Network bridge configuration
# - Systemd services
# - Firewall rules
#
# Run on: Proxmox Host
# Requirements: Root privileges, Proxmox VE 8.x

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/proxmox-computer-control/host"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_proxmox() {
    if ! command -v qm &>/dev/null; then
        log_warn "Proxmox VE not detected. Some features may not work."
    else
        log_info "Proxmox VE detected: $(pveversion 2>/dev/null || echo 'unknown version')"
    fi
}

install_dependencies() {
    log_step "Installing Dependencies"

    apt-get update
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-evdev \
        evemu-tools \
        input-utils \
        socat \
        netcat-openbsd \
        iptables \
        iptables-persistent

    log_info "Dependencies installed"
}

install_python_packages() {
    log_step "Installing Python Packages"

    pip3 install --upgrade pip
    pip3 install evdev

    log_info "Python packages installed"
}

setup_directories() {
    log_step "Setting Up Directories"

    mkdir -p "$INSTALL_DIR"
    mkdir -p /var/log/proxmox-computer-control
    mkdir -p /etc/proxmox-computer-control

    log_info "Directories created"
}

copy_files() {
    log_step "Copying Files"

    # Copy virtual-hid Python modules
    cp -r "$BASE_DIR/virtual-hid" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/virtual-hid/"*.py

    # Copy network scripts
    cp -r "$BASE_DIR/network" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/network/"*.sh

    # Copy management scripts
    cp -r "$BASE_DIR/scripts" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/scripts/"*.sh

    log_info "Files copied to $INSTALL_DIR"
}

configure_services() {
    log_step "Configuring Systemd Services"

    # Copy service files
    cp "$BASE_DIR/services/"*.service /etc/systemd/system/

    # Reload systemd
    systemctl daemon-reload

    # Enable services
    systemctl enable virtual-hid.service
    systemctl enable input-router.service
    # vnc-bridge is optional, don't enable by default
    # systemctl enable vnc-bridge.service

    log_info "Services configured"
}

setup_network() {
    log_step "Setting Up Network Bridge"

    bash "$INSTALL_DIR/network/vmbr1_config.sh" setup

    log_info "Network bridge configured"
}

setup_firewall() {
    log_step "Configuring Firewall"

    bash "$INSTALL_DIR/network/firewall_rules.sh" setup

    log_info "Firewall configured"
}

setup_uhid_permissions() {
    log_step "Setting Up UHID Permissions"

    # Create udev rule for uhid access
    cat > /etc/udev/rules.d/99-uhid.rules << 'EOF'
# Allow access to UHID device for virtual HID creation
KERNEL=="uhid", MODE="0666"
KERNEL=="uinput", MODE="0666"
EOF

    # Reload udev rules
    udevadm control --reload-rules
    udevadm trigger

    # Load uhid module
    modprobe uhid
    echo "uhid" >> /etc/modules-load.d/uhid.conf

    log_info "UHID permissions configured"
}

create_config() {
    log_step "Creating Configuration"

    cat > /etc/proxmox-computer-control/host.conf << 'EOF'
# Proxmox Computer Control - Host Configuration

[network]
bridge_name = vmbr1
bridge_ip = 192.168.100.1
netmask = 24
windows_vm_ip = 192.168.100.100
ubuntu_vm_ip = 192.168.100.101

[hid_controller]
mouse_port = 8888
keyboard_port = 8889
bind_address = 0.0.0.0

[jitter]
enabled = true
min_delay_ms = 1.0
max_delay_ms = 5.0
movement_jitter_px = 2

[logging]
level = INFO
file = /var/log/proxmox-computer-control/host.log
EOF

    log_info "Configuration created at /etc/proxmox-computer-control/host.conf"
}

print_summary() {
    log_step "Installation Complete"

    echo "Installed components:"
    echo "  - Virtual HID device creator"
    echo "  - HID command router (TCP)"
    echo "  - Network bridge (vmbr1)"
    echo "  - Firewall rules"
    echo ""
    echo "Services:"
    echo "  - virtual-hid.service (enabled)"
    echo "  - input-router.service (enabled)"
    echo "  - vnc-bridge.service (available, not enabled)"
    echo ""
    echo "Next steps:"
    echo "  1. Create Windows VM (ID 100) and Ubuntu VM (ID 101)"
    echo "  2. Configure VMs to use vmbr1 for second NIC"
    echo "  3. Start services: systemctl start input-router"
    echo "  4. Set up Windows VM with w10-drivers scripts"
    echo "  5. Set up Ubuntu VM with ubu-cont scripts"
    echo ""
    echo "Management:"
    echo "  - Start: $INSTALL_DIR/scripts/start_all.sh"
    echo "  - Status: $INSTALL_DIR/scripts/status.sh"
    echo "  - Logs: journalctl -u input-router -f"
}

main() {
    check_root
    check_proxmox

    log_step "Starting Installation"
    echo "Installing Proxmox Computer Control - Host Components"
    echo "Base directory: $BASE_DIR"
    echo "Install directory: $INSTALL_DIR"
    echo ""

    install_dependencies
    install_python_packages
    setup_directories
    copy_files
    configure_services
    setup_network
    setup_firewall
    setup_uhid_permissions
    create_config
    print_summary
}

# Run main
main "$@"
