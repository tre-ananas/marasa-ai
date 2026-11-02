<#
.SYNOPSIS
    Serves Marasa AI to your local network (one port, one process).

.DESCRIPTION
    Builds the frontend and serves it, together with the API, from FastAPI on
    0.0.0.0:8000. Any device on the same Wi-Fi can open the app from a phone
    or tablet; the session is shared, so you can start on the computer and
    continue on the phone.

    Voice input needs a secure context (HTTPS) and will not work over plain
    HTTP on a LAN address — typing works, which is the point of using a phone.

.PARAMETER Port
    Port to serve on (default 8000).

.EXAMPLE
    .\scripts\serve.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8000
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

function Get-LanAddresses {
    try {
        return @(
            Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
                Where-Object {
                    $_.IPAddress -notlike "127.*" -and
                    $_.IPAddress -notlike "169.254.*" -and
                    $_.PrefixOrigin -ne "WellKnown"
                } |
                Sort-Object InterfaceMetric |
                Select-Object -ExpandProperty IPAddress
        )
    } catch {
        return @()
    }
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

Write-Step "Serving on http://0.0.0.0:$Port"
Write-Note "One session is shared by every device on the network."
Write-Note "Access log: $serverLog"

$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$serverLog = Join-Path $logDir "serve.log"

Push-Location (Join-Path $root "backend")
try {
    # Write the access log to a file so you can see requests from other
    # devices (tail it with: Get-Content data\logs\serve.log -Wait)
    uv run uvicorn app.main:app --host 0.0.0.0 --port $Port *> $serverLog
} finally {
    Pop-Location
}

Write-Host "`nMarasa stopped." -ForegroundColor Green
