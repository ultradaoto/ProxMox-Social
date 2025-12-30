#!/bin/bash
# install_models.sh - Download AI models for the controller
#
# Run on: Ubuntu AI Controller VM
# Requirements: Internet access, ~10GB disk space

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="$BASE_DIR/models"

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

install_ollama() {
    log_info "Installing Ollama..."

    if command -v ollama &>/dev/null; then
        log_info "Ollama already installed"
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi

    # Start Ollama service
    if ! pgrep -x "ollama" > /dev/null; then
        log_info "Starting Ollama service..."
        ollama serve &
        sleep 5
    fi
}

install_vision_models() {
    log_info "Installing vision models via Ollama..."

    # Qwen VL - Vision Language Model
    log_info "Pulling qwen2.5-vl:7b (this may take a while)..."
    ollama pull qwen2.5-vl:7b

    # Alternative: LLaVA
    # log_info "Pulling llava:7b..."
    # ollama pull llava:7b

    log_info "Vision models installed"
}

download_omniparser() {
    log_info "Setting up OmniParser..."

    mkdir -p "$MODELS_DIR"
    cd "$MODELS_DIR"

    # Check if already downloaded
    if [[ -f "omniparser_v2.pt" ]]; then
        log_info "OmniParser model already exists"
        return
    fi

    # Clone OmniParser repository
    if [[ ! -d "OmniParser" ]]; then
        log_info "Cloning OmniParser repository..."
        git clone https://github.com/microsoft/OmniParser.git
    fi

    cd OmniParser

    # Install OmniParser dependencies
    pip install -r requirements.txt

    # Download pretrained weights
    log_info "Downloading OmniParser weights..."
    # Note: Update URL when official release is available
    # wget -O ../omniparser_v2.pt "https://github.com/microsoft/OmniParser/releases/download/v2.0/omniparser_v2.pt"

    log_warn "OmniParser model download may require manual steps."
    log_warn "Check https://github.com/microsoft/OmniParser for latest instructions."

    cd "$BASE_DIR"
}

install_ocr() {
    log_info "Setting up OCR..."

    # Tesseract (system package)
    if ! command -v tesseract &>/dev/null; then
        log_info "Installing Tesseract..."
        sudo apt-get update
        sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
    fi

    # EasyOCR downloads models on first use
    log_info "EasyOCR will download models on first use"
}

create_model_symlinks() {
    log_info "Creating model symlinks..."

    cd "$MODELS_DIR"

    # Create .gitkeep
    touch .gitkeep

    # Add .gitignore for large files
    cat > .gitignore << 'EOF'
# Ignore large model files
*.pt
*.pth
*.bin
*.onnx
*.safetensors
OmniParser/
!.gitkeep
EOF

    log_info "Model directory configured"
}

verify_installation() {
    log_info "Verifying installation..."

    # Check Ollama
    if ollama list | grep -q "qwen2.5-vl"; then
        log_info "Qwen VL model: OK"
    else
        log_warn "Qwen VL model: NOT FOUND"
    fi

    # Check Tesseract
    if command -v tesseract &>/dev/null; then
        log_info "Tesseract: OK ($(tesseract --version | head -1))"
    else
        log_warn "Tesseract: NOT FOUND"
    fi

    # Check OmniParser
    if [[ -f "$MODELS_DIR/omniparser_v2.pt" ]]; then
        log_info "OmniParser model: OK"
    else
        log_warn "OmniParser model: NOT FOUND (optional)"
    fi
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  all       Install all models (default)"
    echo "  ollama    Install Ollama and vision models"
    echo "  omni      Download OmniParser"
    echo "  ocr       Install OCR components"
    echo "  verify    Verify installation"
    echo ""
}

case "${1:-all}" in
    all)
        install_ollama
        install_vision_models
        download_omniparser
        install_ocr
        create_model_symlinks
        verify_installation
        ;;
    ollama)
        install_ollama
        install_vision_models
        ;;
    omni)
        download_omniparser
        ;;
    ocr)
        install_ocr
        ;;
    verify)
        verify_installation
        ;;
    *)
        usage
        exit 1
        ;;
esac

log_info "Model installation complete!"
