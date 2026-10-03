# Setup Verification Script
# Run this first to ensure everything is configured correctly

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "NEPSE Automation Setup Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Change to script directory
Set-Location $PSScriptRoot

# Test 1: Python
Write-Host "[Test 1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Python not found or not in PATH" -ForegroundColor Red
    $allGood = $false
}
Write-Host ""

# Test 2: Required packages
Write-Host "[Test 2/5] Checking Python packages..." -ForegroundColor Yellow
try {
    $packages = @("httpx", "pandas")
    foreach ($package in $packages) {
        python -c "import $package" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ $package is installed" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $package is NOT installed" -ForegroundColor Red
            $allGood = $false
        }
    }
} catch {
    Write-Host "  ❌ Error checking packages" -ForegroundColor Red
    $allGood = $false
}
Write-Host ""

# Test 3: Git
Write-Host "[Test 3/5] Checking Git..." -ForegroundColor Yellow
try {
    $gitVersion = git --version 2>&1
    Write-Host "  ✅ Git found: $gitVersion" -ForegroundColor Green
    
    # Check if in a git repo
    $isGitRepo = git rev-parse --is-inside-work-tree 2>&1
    if ($isGitRepo -eq "true") {
        Write-Host "  ✅ Inside a Git repository" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Not inside a Git repository" -ForegroundColor Yellow
        $allGood = $false
    }
} catch {
    Write-Host "  ❌ Git not found or not in PATH" -ForegroundColor Red
    $allGood = $false
}
Write-Host ""

# Test 4: Git Configuration
Write-Host "[Test 4/5] Checking Git configuration..." -ForegroundColor Yellow
try {
    $gitUser = git config user.name
    $gitEmail = git config user.email
    
    if ($gitUser) {
        Write-Host "  ✅ Git user name: $gitUser" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Git user name not set" -ForegroundColor Yellow
        Write-Host "     Run: git config --global user.name 'Your Name'" -ForegroundColor Gray
    }
    
    if ($gitEmail) {
        Write-Host "  ✅ Git email: $gitEmail" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Git email not set" -ForegroundColor Yellow
        Write-Host "     Run: git config --global user.email 'your@email.com'" -ForegroundColor Gray
    }
    
    $credHelper = git config credential.helper
    if ($credHelper) {
        Write-Host "  ✅ Credential helper: $credHelper" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  No credential helper configured" -ForegroundColor Yellow
        Write-Host "     Run: git config --global credential.helper manager-core" -ForegroundColor Gray
        Write-Host "     Then do one manual 'git push' to save credentials" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ❌ Error checking Git config" -ForegroundColor Red
}
Write-Host ""

# Test 5: Remote Repository
Write-Host "[Test 5/5] Checking GitHub remote..." -ForegroundColor Yellow
try {
    $gitRemote = git remote get-url origin 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Remote URL: $gitRemote" -ForegroundColor Green
        
        # Check if we can reach GitHub
        Write-Host "  Testing connection to GitHub..." -ForegroundColor Gray
        $testFetch = git ls-remote --heads origin 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Successfully connected to GitHub" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Cannot connect to GitHub (check credentials/internet)" -ForegroundColor Red
            Write-Host "     $testFetch" -ForegroundColor Gray
            $allGood = $false
        }
    } else {
        Write-Host "  ❌ No remote repository configured" -ForegroundColor Red
        $allGood = $false
    }
} catch {
    Write-Host "  ❌ Error checking remote" -ForegroundColor Red
    $allGood = $false
}
Write-Host ""

# Final Summary
Write-Host "========================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✅ ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You're ready to set up automation!" -ForegroundColor Green
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Test the script manually: run_and_push.ps1" -ForegroundColor White
    Write-Host "  2. Follow AUTOMATION_GUIDE.md to set up Task Scheduler" -ForegroundColor White
    Write-Host "  3. Or push .github/workflows/auto-update.yml for GitHub Actions" -ForegroundColor White
} else {
    Write-Host "⚠️  SOME CHECKS FAILED" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please fix the issues above before setting up automation." -ForegroundColor Yellow
    Write-Host "See AUTOMATION_GUIDE.md for troubleshooting help." -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Optional: Offer to install missing packages
python -c "import httpx, pandas" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Would you like to install missing Python packages now? (Y/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq "Y" -or $response -eq "y") {
        Write-Host "Installing packages from requirements.txt..." -ForegroundColor Cyan
        pip install -r requirements.txt
        Write-Host ""
        Write-Host "✅ Packages installed! Run this script again to verify." -ForegroundColor Green
    }
}

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
