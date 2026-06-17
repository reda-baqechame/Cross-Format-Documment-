# One-command local dev on Windows: postgres + migrations + API + web.
# Usage: .\scripts\dev.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example"
}

Write-Host "Starting postgres + redis..."
docker compose up -d postgres redis

Write-Host "Applying migrations..."
Push-Location backend
uv run alembic upgrade head
Pop-Location

Write-Host "Starting API on http://127.0.0.1:8000 ..."
$apiJob = Start-Job -ScriptBlock {
  Set-Location $using:Root
  Set-Location backend
  uv run uvicorn docos.main:app --reload --host 127.0.0.1 --port 8000 2>&1
}

Start-Sleep -Seconds 3
try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5
  Write-Host "API ready: $($health.status)"
} catch {
  Write-Warning "API not responding yet — check the job output: Receive-Job -Id $($apiJob.Id)"
}

Write-Host "Starting web on http://localhost:3100 ..."
Write-Host "Press Ctrl+C to stop. Then run: Stop-Job -Id $($apiJob.Id); Remove-Job -Id $($apiJob.Id)"

pnpm --filter @docos/web dev

Stop-Job -Id $apiJob.Id -ErrorAction SilentlyContinue
Remove-Job -Id $apiJob.Id -ErrorAction SilentlyContinue
