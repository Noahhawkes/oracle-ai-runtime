$ErrorActionPreference = "Stop"

Write-Host "Checking ORACLE at http://127.0.0.1:7777/api/mode ..." -ForegroundColor Cyan
try {
    $mode = Invoke-RestMethod -Uri "http://127.0.0.1:7777/api/mode" -TimeoutSec 5
    Write-Host "ORACLE is online. Mode: $($mode.mode)" -ForegroundColor Green
} catch {
    Write-Host "ORACLE is not reachable on localhost:7777." -ForegroundColor Red
    Write-Host "Start ORACLE first, then run this script again."
    exit 1
}

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tailscale) {
    Write-Host "Tailscale CLI was not found. Install Tailscale for Windows and sign in first." -ForegroundColor Red
    exit 1
}

Write-Host "Publishing localhost:7777 privately inside your tailnet over HTTPS..." -ForegroundColor Cyan
& tailscale serve --bg localhost:7777
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "" 
Write-Host "Private ORACLE phone address:" -ForegroundColor Green
& tailscale serve status
Write-Host "" 
Write-Host "Paste the HTTPS address into ORACLE Mobile > Settings." -ForegroundColor Yellow
Write-Host "Do NOT use Tailscale Funnel and do NOT port-forward 7777." -ForegroundColor Yellow
