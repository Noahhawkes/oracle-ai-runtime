# ORACLE.AI — GitHub First Push Script
# Run this once to back up the repo to GitHub
# Takes about 4 minutes total including creating the repo

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ORACLE.AI — GitHub Backup Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "STEP 1: Create the GitHub repo first (if you have not):" -ForegroundColor Yellow
Write-Host "  1. Go to https://github.com/new" -ForegroundColor White
Write-Host "  2. Repository name: ORACLE.AI" -ForegroundColor White
Write-Host "  3. Set to PRIVATE" -ForegroundColor White
Write-Host "  4. Do NOT check 'Initialize with README'" -ForegroundColor White
Write-Host "  5. Click Create repository" -ForegroundColor White
Write-Host ""
Write-Host "STEP 2: Enter your GitHub username below." -ForegroundColor Yellow
Write-Host ""

$username = Read-Host "GitHub username"

if ([string]::IsNullOrWhiteSpace($username)) {
    Write-Host "No username entered. Exiting." -ForegroundColor Red
    exit 1
}

$repoUrl = "https://github.com/$username/ORACLE.AI.git"

Write-Host ""
Write-Host "Will push to: $repoUrl" -ForegroundColor Green
Write-Host ""

$confirm = Read-Host "Press ENTER to continue or type 'cancel' to stop"
if ($confirm -eq "cancel") { exit 0 }

Push-Location "G:\My Drive\HawkesNest LLC\ORACLE.AI"

Write-Host ""
Write-Host "Adding remote..." -ForegroundColor Cyan
git remote remove origin 2>$null
git remote add origin $repoUrl

Write-Host "Setting branch to main..." -ForegroundColor Cyan
git branch -M main

Write-Host "Pushing to GitHub..." -ForegroundColor Cyan
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "   SUCCESS — ORACLE.AI is on GitHub!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "View it at: https://github.com/$username/ORACLE.AI" -ForegroundColor White
    Write-Host ""
    Write-Host "Future pushes (after new commits):" -ForegroundColor Yellow
    Write-Host "   git push" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Push failed. Common fixes:" -ForegroundColor Red
    Write-Host "  - Make sure you created the repo on GitHub first" -ForegroundColor White
    Write-Host "  - Make sure the repo is named exactly: ORACLE.AI" -ForegroundColor White
    Write-Host "  - If prompted for credentials, use a GitHub Personal Access Token" -ForegroundColor White
    Write-Host "    Get one at: https://github.com/settings/tokens (scopes: repo)" -ForegroundColor White
}

Pop-Location
Write-Host ""
Write-Host "Press any key to close..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
