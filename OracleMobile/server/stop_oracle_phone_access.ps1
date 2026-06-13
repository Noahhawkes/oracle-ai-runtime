$ErrorActionPreference = "Stop"
Write-Host "Removing ORACLE's Tailscale Serve configuration..." -ForegroundColor Cyan
& tailscale serve reset
if ($LASTEXITCODE -eq 0) {
    Write-Host "ORACLE phone access is disabled." -ForegroundColor Green
}
