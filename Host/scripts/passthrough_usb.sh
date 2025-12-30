#!/bin/bash
# passthrough_usb.sh - Configure USB passthrough for virtual HID devices
#
# This script helps configure USB passthrough from the Proxmox host to the Windows VM,
# allowing the virtual Logitech devices to appear as real USB devices in Windows.
#
# Run on: Proxmox Host
# Requirements: Root privileges, Windows VM created

set -e

WINDOWS_VM_ID="${1:-101}"
LOGITECH_VENDOR_ID="046d"
LOGITECH_MOUSE_PRODUCT_ID="c52b"
LOGITECH_KEYBOARD_PRODUCT_ID="c534"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

list_usb_devices() {
    log_step "Available USB Devices"

    echo "Logitech devices found:"
    lsusb | grep -i logitech || echo "  (none)"

    echo ""
    echo "All USB devices:"
    lsusb

    echo ""
    echo "Virtual input devices:"
    ls -la /dev/input/by-id/ 2>/dev/null | head -20 || echo "  (none)"
}

find_virtual_devices() {
    log_step "Finding Virtual HID Devices"

    # Find devices by checking /proc/bus/input/devices
    echo "Looking for virtual Logitech devices in kernel..."

    if grep -l "Logitech" /sys/class/input/*/device/name 2>/dev/null; then
        log_info "Found virtual Logitech device(s)"
        grep -l "Logitech" /sys/class/input/*/device/name 2>/dev/null | while read f; do
            echo "  $f: $(cat "$f")"
        done
    else
        log_warn "No virtual Logitech devices found"
        echo "Make sure virtual-hid.service is running"
    fi
}

generate_vm_config() {
    log_step "Generating VM Configuration"

    VM_CONF="/etc/pve/qemu-server/${WINDOWS_VM_ID}.conf"

    if [[ ! -f "$VM_CONF" ]]; then
        log_error "VM configuration not found: $VM_CONF"
        log_error "Please create Windows VM with ID $WINDOWS_VM_ID first"
        return 1
    fi

    log_info "Current VM config: $VM_CONF"
    echo ""

    # Check if USB devices already configured
    if grep -q "usb.*host=" "$VM_CONF"; then
        log_warn "USB passthrough already configured:"
        grep "usb.*host=" "$VM_CONF"
        echo ""
        read -p "Remove existing USB config and reconfigure? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Remove existing USB lines
            sed -i '/^usb[0-9]*:/d' "$VM_CONF"
            log_info "Removed existing USB configuration"
        else
            return 0
        fi
    fi

    # Add USB passthrough for virtual Logitech devices
    echo "" >> "$VM_CONF"
    echo "# Virtual Logitech HID devices for AI control" >> "$VM_CONF"
    echo "usb0: host=${LOGITECH_VENDOR_ID}:${LOGITECH_MOUSE_PRODUCT_ID},usb3=1" >> "$VM_CONF"
    echo "usb1: host=${LOGITECH_VENDOR_ID}:${LOGITECH_KEYBOARD_PRODUCT_ID},usb3=1" >> "$VM_CONF"

    log_info "Added USB passthrough configuration:"
    echo "  usb0: Logitech Mouse (VID:${LOGITECH_VENDOR_ID} PID:${LOGITECH_MOUSE_PRODUCT_ID})"
    echo "  usb1: Logitech Keyboard (VID:${LOGITECH_VENDOR_ID} PID:${LOGITECH_KEYBOARD_PRODUCT_ID})"
}

configure_usb_controller() {
    log_step "Configuring USB Controller"

    VM_CONF="/etc/pve/qemu-server/${WINDOWS_VM_ID}.conf"

    if [[ ! -f "$VM_CONF" ]]; then
        log_error "VM configuration not found: $VM_CONF"
        return 1
    fi

    # Check if USB controller is configured for USB 3.0
    if grep -q "machine.*q35" "$VM_CONF"; then
        log_info "Q35 machine type detected (supports USB 3.0)"
    else
        log_warn "Consider using Q35 machine type for better USB 3.0 support"
    fi

    # Add XHCI controller if not present
    if ! grep -q "usb.*xhci" "$VM_CONF"; then
        log_info "Note: USB 3.0 XHCI controller will be added automatically"
    fi
}

verify_passthrough() {
    log_step "Verification"

    echo "To verify USB passthrough:"
    echo ""
    echo "1. Start the Windows VM:"
    echo "   qm start $WINDOWS_VM_ID"
    echo ""
    echo "2. Check Device Manager in Windows for:"
    echo "   - Logitech USB Receiver (Mouse)"
    echo "   - Logitech USB Receiver (Keyboard)"
    echo ""
    echo "3. On Proxmox host, verify devices are bound to VM:"
    echo "   lsusb | grep Logitech"
    echo ""
    echo "4. Test input by sending commands from Ubuntu VM:"
    echo "   echo '{\"type\":\"mouse_move\",\"x\":10,\"y\":0}' | nc 192.168.100.1 8888"
}

usage() {
    echo "Usage: $0 [vm_id] [command]"
    echo ""
    echo "Arguments:"
    echo "  vm_id     Windows VM ID (default: 101)"
    echo ""
    echo "Commands:"
    echo "  list      List USB devices"
    echo "  find      Find virtual HID devices"
    echo "  config    Generate VM USB passthrough config"
    echo "  verify    Show verification steps"
    echo "  all       Run all steps (default)"
    echo ""
    echo "Examples:"
    echo "  $0 101 list    - List USB devices for VM 101"
    echo "  $0 101 config  - Configure USB passthrough for VM 101"
}

main() {
    check_root

    # Parse arguments
    if [[ "$1" =~ ^[0-9]+$ ]]; then
        WINDOWS_VM_ID="$1"
        shift
    fi

    COMMAND="${1:-all}"

    echo "Proxmox USB Passthrough Configuration"
    echo "======================================"
    echo "Windows VM ID: $WINDOWS_VM_ID"
    echo ""

    case "$COMMAND" in
        list)
            list_usb_devices
            ;;
        find)
            find_virtual_devices
            ;;
        config)
            generate_vm_config
            configure_usb_controller
            ;;
        verify)
            verify_passthrough
            ;;
        all)
            list_usb_devices
            find_virtual_devices
            generate_vm_config
            configure_usb_controller
            verify_passthrough
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
