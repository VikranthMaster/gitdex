#!/bin/sh
# install.sh — one-shot installer for repo-summarizer
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/<you>/<repo>/main/install.sh | sh
#
# Installs (only what's missing):
#   1. Python 3.9+
#   2. pipx
#   3. Ollama
#   4. qwen2.5:0.5b model (pulled via Ollama)
#   5. This CLI, via pipx, from GitHub
#
# Supports: macOS, Debian/Ubuntu, Fedora/RHEL, Arch. Windows -> run under WSL.

set -e

REPO_URL="https://github.com/VikranthMaster/gitdex.git"   # <-- change this
PKG_ENTRYPOINT="gitdex"
OLLAMA_MODEL="qwen2.5:0.5b"

# ---------- helpers ----------

info()  { printf '\033[1;34m[info]\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m[ok]\033[0m %s\n'   "$1"; }
warn()  { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
err()   { printf '\033[1;31m[error]\033[0m %s\n' "$1"; }

has() { command -v "$1" >/dev/null 2>&1; }

# ---------- OS detection ----------

OS="unknown"
PKG_MGR="unknown"

case "$(uname -s)" in
    Darwin)
        OS="macos"
        ;;
    Linux)
        OS="linux"
        if has apt-get; then PKG_MGR="apt"
        elif has dnf; then PKG_MGR="dnf"
        elif has yum; then PKG_MGR="yum"
        elif has pacman; then PKG_MGR="pacman"
        else PKG_MGR="unknown"
        fi
        ;;
    MINGW*|MSYS*|CYGWIN*)
        err "Detected Windows via a Unix-like shell (Git Bash/MSYS/Cygwin)."
        err "Use the Windows installer instead. Open PowerShell as Administrator and run:"
        err '  irm https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install.ps1 | iex'
        err "(Alternatively, install under WSL: wsl --install, then re-run this .sh script there.)"
        exit 1
        ;;
    *)
        err "Unsupported OS: $(uname -s)"
        exit 1
        ;;
esac

info "Detected OS: $OS ${PKG_MGR:+(package manager: $PKG_MGR)}"

# ---------- 1. Python ----------

install_python() {
    info "Installing Python 3..."
    case "$OS" in
        macos)
            if ! has brew; then
                info "Homebrew not found, installing it first..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
            fi
            brew install python
            ;;
        linux)
            case "$PKG_MGR" in
                apt)    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv ;;
                dnf)    sudo dnf install -y python3 python3-pip ;;
                yum)    sudo yum install -y python3 python3-pip ;;
                pacman) sudo pacman -Sy --noconfirm python python-pip ;;
                *)      err "No supported package manager found. Install Python 3.9+ manually, then re-run."; exit 1 ;;
            esac
            ;;
    esac
}

if has python3; then
    PY_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    ok "Python $PY_VER found."
else
    warn "Python 3 not found."
    install_python
    ok "Python installed."
fi

# ---------- 2. pipx ----------

if has pipx; then
    ok "pipx already installed."
else
    info "Installing pipx..."
    python3 -m pip install --user --break-system-packages pipx 2>/dev/null || python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    # make pipx available in this same shell session without reopening terminal
    export PATH="$PATH:$HOME/.local/bin"
    ok "pipx installed."
fi

# ---------- 3. Ollama ----------

if has ollama; then
    ok "Ollama already installed."
else
    info "Installing Ollama..."
    case "$OS" in
        macos)
            if has brew; then
                brew install ollama
            else
                curl -fsSL https://ollama.com/install.sh | sh
            fi
            ;;
        linux)
            curl -fsSL https://ollama.com/install.sh | sh
            ;;
    esac
    ok "Ollama installed."
fi

# Make sure the Ollama server is running before we pull a model
if ! pgrep -x "ollama" >/dev/null 2>&1; then
    info "Starting Ollama server in the background..."
    nohup ollama serve >/tmp/ollama.log 2>&1 &
    sleep 3
fi

# ---------- 4. Pull the model ----------

info "Pulling model $OLLAMA_MODEL (this may take a few minutes)..."
ollama pull "$OLLAMA_MODEL"
ok "Model $OLLAMA_MODEL ready."

# ---------- 5. Install the CLI itself ----------

info "Installing $PKG_ENTRYPOINT via pipx from $REPO_URL..."
pipx install "git+${REPO_URL}" --force
ok "$PKG_ENTRYPOINT installed."

# ---------- done ----------

echo ""
ok "All set! Try running:"
echo "    $PKG_ENTRYPOINT help"
echo ""
warn "If the command isn't found, open a new terminal (or run: source ~/.bashrc / ~/.zshrc) so PATH updates take effect."
