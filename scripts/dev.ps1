<#
.SYNOPSIS
    Runs the Marasa AI backend and frontend together.

.DESCRIPTION
    Starts the FastAPI backend on 127.0.0.1:8000 and the Vite dev server on
    127.0.0.1:5173. Press Ctrl+C to stop both.
#>
[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

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

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is missing. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is missing. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Step "Starting backend on http://127.0.0.1:$BackendPort"
$backendPort = Get-FreePort $BackendPort
$frontendPort = Get-FreePort $FrontendPort
$env:MARASA_BACKEND_PORT = "$backendPort"
$env:MARASA_FRONTEND_PORT = "$frontendPort"

$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$backendLog = Join-Path $logDir "backend.log"
$backendLogErr = Join-Path $logDir "backend.error.log"
$frontendLog = Join-Path $logDir "frontend.log"
$frontendLogErr = Join-Path $logDir "frontend.error.log"

$backend = Start-Process -FilePath "uv" `
    -ArgumentList "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort", "--reload" `
    -WorkingDirectory (Join-Path $root "backend") `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendLogErr `
    -PassThru

Write-Step "Starting frontend on http://127.0.0.1:$frontendPort"
# `npm` resolves to npm.ps1 on Windows, which Start-Process cannot launch
# directly; use the sibling npm.cmd next to node.exe.
$nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
$npmExe = if ($nodeExe) { Join-Path (Split-Path $nodeExe) "npm.cmd" } else { "npm" }
if (-not (Test-Path $npmExe)) { $npmExe = "npm" }
$frontend = Start-Process -FilePath $npmExe `
    -ArgumentList "run", "dev", "--", "--port", "$frontendPort" `
    -WorkingDirectory (Join-Path $root "frontend") `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendLogErr `
    -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/api/health" -TimeoutSec 2
            $ready = $true
            break
        } catch { }
    }
    if ($ready) {
        Write-Host "`nMarasa is running." -ForegroundColor Green
        Write-Host "  App:     http://127.0.0.1:$frontendPort"
        Write-Host "  Backend: http://127.0.0.1:$backendPort/api/health"
        Write-Host "  Provider: $($health.provider) / $($health.model)  (key configured: $($health.key_configured))"
    } else {
        Write-Host "The backend did not come up in time. Check $backendLogErr" -ForegroundColor Yellow
    }
    Write-Host "  Logs:     $logDir"
    Write-Host "Press Ctrl+C to stop."
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    foreach ($process in @($backend, $frontend)) {
        if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
}
