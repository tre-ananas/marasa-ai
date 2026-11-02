<#
.SYNOPSIS
    One-command setup for Marasa AI on Windows.

.DESCRIPTION
    Installs every dependency into project-local, reproducible locations:
      - backend/.venv  (created and locked by uv, from backend/uv.lock)
      - frontend/node_modules (from frontend/package-lock.json)

    Nothing is installed system-wide except uv itself (if it is missing) and
    Node.js (only if it is missing and Scoop is available).

.PARAMETER WithChromium
    Download Playwright's Chromium for PDF rendering. By default Marasa uses
    the Microsoft Edge already installed on Windows, so nothing is downloaded.

.PARAMETER SkipFrontend
    Skip the frontend install (backend-only development).
#>
[CmdletBinding()]
param(
    [switch]$WithChromium,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Write-Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Write-Note($message) { Write-Host "    $message" -ForegroundColor DarkGray }
function Fail($message) {
    Write-Host "`n!! $message" -ForegroundColor Red
    exit 1
}

Set-Location $root

# A shell that was opened before Node.js/uv were installed still has the old
# PATH; refresh it from the persisted environment so the checks below are
# accurate.
function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (($machine, $user) -join ';') + ';' + $env:Path
}
Update-SessionPath

# --- Python -----------------------------------------------------------------
Write-Step "Checking Python"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { Fail "Python 3.12+ is required but was not found. Install it from python.org and re-run." }
$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([int]($pythonVersion.Split('.')[0]) -lt 3 -or [int]($pythonVersion.Split('.')[1]) -lt 12) {
    Fail "Python 3.12+ is required (found $pythonVersion). uv can install it for you: 'uv python install 3.12'."
}
Write-Note "python $pythonVersion"

# --- uv ---------------------------------------------------------------------
Write-Step "Checking uv (Python package manager)"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Note "installing uv via pip..."
    python -m pip install --user --quiet uv
    $uvPath = Join-Path $env:APPDATA "Python\PythonScripts\uv.exe"
    if (Test-Path $uvPath) { $env:Path = "$env:APPDATA\Python\PythonScripts;$env:Path" }
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "uv could not be installed. Install it from https://docs.astral.sh/uv/ and re-run."
}
Write-Note (& uv --version)

# --- Backend ----------------------------------------------------------------
Write-Step "Installing backend dependencies (uv sync)"
Push-Location (Join-Path $root "backend")
uv sync
if ($LASTEXITCODE -ne 0) { Fail "uv sync failed. See the output above." }
if ($WithChromium) {
    Write-Note "installing Playwright Chromium (this downloads ~150 MB)..."
    uv run playwright install chromium
} else {
    Write-Note "PDF rendering will use Microsoft Edge (no download). Re-run with -WithChromium to use Playwright's Chromium."
}
Pop-Location

# --- Node / frontend --------------------------------------------------------
if (-not $SkipFrontend) {
    Write-Step "Checking Node.js"
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        if (Get-Command scoop -ErrorAction SilentlyContinue) {
            Write-Note "installing Node.js with Scoop..."
            scoop install nodejs
            $env:Path = "$env:USERPROFILE\scoop\apps\nodejs\current;$env:Path"
            $node = Get-Command node -ErrorAction SilentlyContinue
        } else {
            Fail "Node.js 20+ is required to build the frontend. Install it from nodejs.org and re-run."
        }
    }
    if ($node) {
        $nodeVersion = (& node --version) -replace '^v', ''
        if ([int]($nodeVersion.Split('.')[0]) -lt 20) {
            Fail "Node.js 20+ is required (found $nodeVersion)."
        }
        Write-Note "node $nodeVersion"

        Write-Step "Installing frontend dependencies (npm ci)"
        Push-Location (Join-Path $root "frontend")
        npm ci
        if ($LASTEXITCODE -ne 0) {
            Fail "npm ci failed. Close any running Vite dev server (it locks native modules) and re-run."
        }
        Pop-Location
    }
}

# --- Configuration ----------------------------------------------------------
Write-Step "Preparing configuration"
if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
    Write-Note "created .env from .env.example"
} else {
    Write-Note ".env already exists (left untouched)"
}
$rubric = Join-Path $root "OPI-Familiarization-Guide-2020-1.pdf"
if (Test-Path $rubric) {
    Write-Note "found the ACTFL OPI Familiarization Guide at the repo root"
} else {
    Write-Note "ACTFL OPI Familiarization Guide not found (optional; used to keep the rubric faithful)"
}

# --- Verify -----------------------------------------------------------------
Write-Step "Verifying the installation"
Push-Location (Join-Path $root "backend")
uv run python -c "from app.main import app; print('backend OK:', app.title)"
uv run pytest -q | Select-Object -Last 3
Pop-Location

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "  Start everything:  scripts\dev.ps1"
Write-Host "  Run the tests:     scripts\test.ps1"
Write-Host "  Then open:         http://localhost:5173"
Write-Host ""
