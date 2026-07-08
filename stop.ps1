<#
.SYNOPSIS
  Stop every service started by start.ps1.

.DESCRIPTION
  Kills the uvicorn (backend), next dev server (frontend), and the
  WhatsApp connector node process by port. Saves you from hunting
  through Task Manager.
#>

$ErrorActionPreference = 'SilentlyContinue'

function Stop-Port {
    param([int]$Port, [string]$Label)
    $servicePids = (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($servicePids) {
        foreach ($servicePid in $servicePids) {
            Write-Host "Stopping $Label (pid $servicePid, port $Port)..." -ForegroundColor Yellow
            Stop-Process -Id $servicePid -Force
        }
    } else {
        Write-Host "$Label (port $Port) - not running." -ForegroundColor DarkGray
    }
}

Stop-Port -Port 3000 -Label 'Frontend (Next.js)'
Stop-Port -Port 8000 -Label 'Backend (uvicorn)'
Stop-Port -Port 3001 -Label 'WhatsApp connector'

Write-Host ''
Write-Host 'All Knowtis services stopped.' -ForegroundColor Green
