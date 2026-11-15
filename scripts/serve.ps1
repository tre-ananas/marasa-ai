<#
.SYNOPSIS
    Serves Marasa AI locally on this device (one port, one process).

.DESCRIPTION
    Builds the frontend and serves it together with the API from FastAPI on
    127.0.0.1. The app is intentionally not exposed to the LAN or the
    internet. OpenCode Go credentials live only in memory for the signed-in
    browser session.

.PARAMETER Port
    Port to serve on (default 8787, so Marasa never takes port 8000 from
    another app).

.EXAMPLE
    .\scripts\serve.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8787
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Write-Note($message) { Write-Host "    $message" -ForegroundColor DarkGray }
function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (($machine, $user) -join ';') + ';' + $env:Path
}
Update-SessionPath

function Get-FreePort([int]$Preferred) {
    for ($candidate = $Preferred; $candidate -lt ($Preferred + 20); $candidate++) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate)
            $listener.Start()
            return $candidate
        } catch {
            # port in use, try the next one
        } finally {
            if ($listener) { $listener.Stop() }
        }
    }
    throw "No free port found near $Preferred."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is missing. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is missing. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Step "Building the frontend"
Push-Location (Join-Path $root "frontend")
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "Frontend build failed." -ForegroundColor Red; exit 1 }
Pop-Location

# Never take a port another app is using: 8787 first, then 8788, 8789, ...
$Port = Get-FreePort $Port

Write-Step "Serving on http://127.0.0.1:$Port"
Write-Note "Device-local only; other network devices cannot connect."
Write-Note "OpenCode Go sign-in is required for each browser session."

$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$serverLog = Join-Path $logDir "serve.log"

Push-Location (Join-Path $root "backend")
try {
    uv run uvicorn app.main:app --host 127.0.0.1 --port $Port *> $serverLog
} finally {
    Pop-Location
}

Write-Host "`nMarasa stopped." -ForegroundColor Green
