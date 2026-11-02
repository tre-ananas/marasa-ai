<#
.SYNOPSIS
    Runs the backend (pytest) and frontend (vitest) test suites.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (($machine, $user) -join ';') + ';' + $env:Path
}
Update-SessionPath

$failed = $false

Write-Host "==> Backend tests (pytest)" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
uv run pytest -q
if ($LASTEXITCODE -ne 0) { $failed = $true }
Pop-Location

Write-Host "`n==> Frontend tests (vitest)" -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
npm test
if ($LASTEXITCODE -ne 0) { $failed = $true }
Pop-Location

if ($failed) {
    Write-Host "`nSome tests failed." -ForegroundColor Red
    exit 1
}
Write-Host "`nAll tests passed." -ForegroundColor Green
