# NEPSE Data Auto-Fetch and Push Script (PowerShell)
# This script runs the data fetcher and automatically commits/pushes to GitHub

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "NEPSE Auto-Update Script (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# Step 1: Run Python script
Write-Host "[1/3] Running data fetch script..." -ForegroundColor Yellow
Write-Host ""

try {
    python asyncmain_incremental.py
    
    if ($LASTEXITCODE -ne 0) {
        throw "Python script returned error code: $LASTEXITCODE"
    }
}
catch {
    Write-Host ""
    Write-Host "ERROR: Python script failed!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Check the output above for errors." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/3] Checking for changes..." -ForegroundColor Yellow
Write-Host ""

# Check for changes
$gitStatus = git status --porcelain
if ([string]::IsNullOrWhiteSpace($gitStatus)) {
    Write-Host "No changes detected. Nothing to commit." -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Script completed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    exit 0
}

Write-Host "Changes detected! Proceeding with commit and push..." -ForegroundColor Green
Write-Host ""

# Step 3: Commit and push
Write-Host "[3/3] Committing and pushing to GitHub..." -ForegroundColor Yellow
Write-Host ""

try {
    # Add all changes
    git add .
    
    # Create commit message with current date
    $currentDate = Get-Date -Format "MMMM dd, yyyy"
    $commitMessage = "Data update: $currentDate"
    
    git commit -m $commitMessage
    
    # Push to GitHub
    git push origin master
    
    if ($LASTEXITCODE -ne 0) {
        throw "Git push failed with error code: $LASTEXITCODE"
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "SUCCESS! Data updated and pushed to GitHub" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
}
catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "ERROR: Failed to push to GitHub" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Please check your internet connection and Git credentials" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
exit 0
