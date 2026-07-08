<#
.SYNOPSIS
  Start Knowtis locally. By default this starts only the frontend.

.DESCRIPTION
  Runs selected processes in their own windows, so logs stay separate.
  Closing this terminal does NOT kill the children. Use stop.ps1 to shut
  them down.

.EXAMPLE
  .\start.ps1

.EXAMPLE
  .\start.ps1 -Backend

.EXAMPLE
  .\start.ps1 -All
#>

param(
    [switch]$Backend,
    [switch]$WhatsApp,
    [switch]$All,
    [switch]$NoFrontend,
    [switch]$ReloadBackend
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Start-Knowtis {
    param([string]$Title, [string]$Path, [string]$CommandLine, [int]$Port)

    $existing = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        Write-Host "$Title already appears to be running on port $Port (pid $($existing.OwningProcess)). Skipping." -ForegroundColor Yellow
        return
    }

    Write-Host "Starting $Title in $Path..." -ForegroundColor Cyan

    # Run via cmd.exe /k (keep open) to show live logs in separate windows and avoid Win32 redirection buffering issues.
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/k', $CommandLine `
        -WorkingDirectory $Path
}

$startFrontend = -not $NoFrontend
$startBackend = $Backend -or $All
$startWhatsApp = $WhatsApp -or $All

# Make sure log dir exists.
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null

# ── WhatsApp connector (Node, port 3001) ─────────────────────────────────────
if ($startWhatsApp) {
    $wa = Test-Path -LiteralPath "$root\whatsapp_connector\node_modules"
    if (-not $wa) {
        Write-Host 'Installing whatsapp_connector deps (first run)...' -ForegroundColor Yellow
        Set-Location "$root\whatsapp_connector"
        npm install
        Set-Location $root
    }
    Start-Knowtis -Title 'WhatsApp connector' -Path "$root\whatsapp_connector" -Port 3001 -CommandLine 'npm run start'
}

# ── Backend (FastAPI, port 8000) ─────────────────────────────────────────────
if ($startBackend) {
    $venv = Test-Path -LiteralPath "$root\backend\venv\Scripts\uvicorn.exe"
    if (-not $venv) {
        Write-Host 'Installing backend deps (first run)...' -ForegroundColor Yellow
        if (-not (Test-Path -LiteralPath "$root\backend\venv\Scripts\python.exe")) {
            python -m venv "$root\backend\venv"
        }
        & "$root\backend\venv\Scripts\pip.exe" install -r "$root\backend\requirements.txt"
    }

    $backendCommand = 'set SCHEDULER_ENABLED=false&& set SEMANTIC_PREWARM_ENABLED=false&& "{0}" app.main:app --host 0.0.0.0 --port 8000' -f "$root\backend\venv\Scripts\uvicorn.exe"
    if ($ReloadBackend) {
        $backendCommand = "$backendCommand --reload"
    }
    Start-Knowtis -Title 'Backend API' -Path "$root\backend" -Port 8000 -CommandLine $backendCommand
}

# ── Frontend (Next.js, port 3000) ────────────────────────────────────────────
if ($startFrontend) {
    $fe = Test-Path -LiteralPath "$root\frontend\node_modules\next"
    if (-not $fe) {
        Write-Host 'Installing frontend deps (first run)...' -ForegroundColor Yellow
        Set-Location "$root\frontend"
        npm install
        Set-Location $root
    }
    Start-Knowtis -Title 'Frontend' -Path "$root\frontend" -Port 3000 -CommandLine 'npm run dev'
}

Write-Host ""
Write-Host "Requested services launched:" -ForegroundColor Green
if ($startFrontend) { Write-Host "  Frontend           -> http://localhost:3000" -ForegroundColor Green }
if ($startBackend) { Write-Host "  Backend API        -> http://localhost:8000  (docs at /docs)" -ForegroundColor Green }
if ($startWhatsApp) { Write-Host "  WhatsApp connector -> http://localhost:3001" -ForegroundColor Green }
Write-Host ""
Write-Host "Default mode starts only the frontend. Use -Backend, -WhatsApp, or -All for more." -ForegroundColor Gray
Write-Host ""
Write-Host "To stop all services run: " -ForegroundColor Gray -NoNewline
Write-Host ".\stop.ps1"

