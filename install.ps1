# install.ps1 — Windows installer for gitdex
#
# Usage (run in PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install.ps1 | iex
#
# Installs (only what's missing):
#   1. Chocolatey (package manager)
#   2. Python 3.9+
#   3. pipx
#   4. Ollama
#   5. qwen2.5:0.5b model
#   6. gitdex, via pipx, from GitHub

$ErrorActionPreference = "Stop"

$RepoUrl        = "https://github.com/YOUR_USERNAME/YOUR_REPO.git"   # <-- change this
$PkgEntrypoint  = "gitdex"
$OllamaModel    = "qwen2.5:0.5b"

function Info($msg)  { Write-Host "[info] $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "[ok] $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[warn] $msg" -ForegroundColor Yellow }
function Err($msg)   { Write-Host "[error] $msg" -ForegroundColor Red }

function Test-Admin {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Err "This script needs to run as Administrator (Chocolatey requires it)."
    Err "Right-click PowerShell -> 'Run as Administrator', then re-run this command."
    exit 1
}

function Has-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ---------- 1. Chocolatey ----------

if (Has-Command choco) {
    Ok "Chocolatey already installed."
} else {
    Info "Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Ok "Chocolatey installed."
}

# ---------- 2. Python ----------

if (Has-Command python) {
    $pyVer = (python --version)
    Ok "$pyVer found."
} else {
    Info "Installing Python 3..."
    choco install python3 -y
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Ok "Python installed."
}

# ---------- 3. pipx ----------

if (Has-Command pipx) {
    Ok "pipx already installed."
} else {
    Info "Installing pipx..."
    python -m pip install --user pipx
    python -m pipx ensurepath
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Ok "pipx installed."
}

# ---------- 4. Ollama ----------

if (Has-Command ollama) {
    Ok "Ollama already installed."
} else {
    Info "Installing Ollama..."
    choco install ollama -y
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Ok "Ollama installed."
}

# Ensure Ollama server is running
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    Info "Starting Ollama server in the background..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# ---------- 5. Pull the model ----------

Info "Pulling model $OllamaModel (this may take a few minutes)..."
ollama pull $OllamaModel
Ok "Model $OllamaModel ready."

# ---------- 6. Install the CLI itself ----------

Info "Installing $PkgEntrypoint via pipx from $RepoUrl..."
pipx install "git+$RepoUrl" --force
Ok "$PkgEntrypoint installed."

# ---------- done ----------

Write-Host ""
Ok "All set! Try running:"
Write-Host "    $PkgEntrypoint --help"
Write-Host ""
Warn "If the command isn't found, close and reopen PowerShell so PATH updates take effect."
