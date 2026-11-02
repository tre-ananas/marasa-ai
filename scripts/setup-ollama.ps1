<#
.SYNOPSIS
    Installs and verifies a local Ollama model for Marasa AI.

.DESCRIPTION
    - installs Ollama if it is missing (winget, then Scoop, then the official
      installer);
    - starts `ollama serve` if it is not already listening on 11434;
    - pulls the requested model (default qwen3:8b, ~5 GB);
    - prints the Marasa `.env` lines needed to use it.

.PARAMETER Model
    The model to install. Defaults to qwen3:8b.

.EXAMPLE
    .\scripts\setup-ollama.ps1
    .\scripts\setup-ollama.ps1 -Model qwen3:4b
#>
[CmdletBinding()]
param(
    [string]$Model = "qwen3:8b"
)

$ErrorActionPreference = 'Stop'

function Write-Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Write-Note($message) { Write-Host "    $message" -ForegroundColor DarkGray }
function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (($machine, $user) -join ';') + ';' + $env:Path
}
Update-SessionPath

Write-Step "Checking Ollama"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Note "installing Ollama..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
    } elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
        scoop install ollama
    } else {
        Write-Host "Install Ollama manually from https://ollama.com/download and re-run." -ForegroundColor Red
        exit 1
    }
    Update-SessionPath
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is still not on PATH. Open a new terminal and re-run." -ForegroundColor Red
    exit 1
}
Write-Note (& ollama --version)

Write-Step "Checking the Ollama server"
$running = $false
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 3 | Out-Null
    $running = $true
} catch { }
if (-not $running) {
    Write-Note "starting `ollama serve` in the background..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 2 | Out-Null
            $running = $true
            break
        } catch { }
    }
}
if (-not $running) {
    Write-Host "The Ollama server did not start. Run 'ollama serve' in another terminal." -ForegroundColor Red
    exit 1
}
Write-Note "server is listening on http://127.0.0.1:11434"

Write-Step "Pulling $Model"
$existing = (& ollama list 2>$null) -join "`n"
if ($existing -match [regex]::Escape($Model)) {
    Write-Note "$Model is already installed"
} else {
    & ollama pull $Model
    if ($LASTEXITCODE -ne 0) { Write-Host "ollama pull failed." -ForegroundColor Red; exit 1 }
}

Write-Step "Verifying a real completion"
$body = @{
    model = $Model
    messages = @(@{ role = "user"; content = "Reply with exactly: ready" })
    stream = $false
} | ConvertTo-Json -Depth 5
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/chat" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 180
    Write-Note "model replied: $($response.message.content)"
} catch {
    Write-Host "The model did not answer: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`nOllama is ready." -ForegroundColor Green
Write-Host "  Add this to your .env (or set it in the settings sheet):"
Write-Host "      MARASA_PROVIDER=ollama"
Write-Host "      MARASA_MODEL="
Write-Host "      MARASA_OLLAMA_MODEL=$Model"
Write-Host "      MARASA_OLLAMA_NUM_CTX=8192"
Write-Host ""
