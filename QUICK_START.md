# 🚀 Quick Start - NEPSE Automation

Stop manually running your script! Here's how to automate it on Windows 11.

## ⚡ Super Quick Setup (3 steps)

### Step 1: Verify Your Setup
Right-click `setup_check.ps1` → **Run with PowerShell**

This checks if everything is configured correctly.

### Step 2: Test It Manually
Right-click `run_and_push.ps1` → **Run with PowerShell**

This should fetch data and push to GitHub automatically.

### Step 3: Choose Your Automation Method

**Option A: Windows Task Scheduler** (Local automation)
- Open [AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md)
- Follow the "Windows Task Scheduler" section
- Your laptop will run the script daily at a set time

**Option B: GitHub Actions** (Cloud automation - recommended!)
- Just push the `.github/workflows/auto-update.yml` file to GitHub
- It will automatically run daily on GitHub's servers
- No need for your laptop to be on!

```bash
git add .github/workflows/auto-update.yml
git commit -m "Add automated data fetching workflow"
git push
```

That's it! 🎉

## 📁 Files Created

- `run_and_push.bat` - Simple batch script
- `run_and_push.ps1` - PowerShell script with better output
- `setup_check.ps1` - Verification script
- `.github/workflows/auto-update.yml` - GitHub Actions workflow
- `AUTOMATION_GUIDE.md` - Detailed setup guide
- `QUICK_START.md` - This file!

## 🆘 Troubleshooting

**Git asks for password every time?**
```bash
git config --global credential.helper manager-core
```
Then do one manual `git push` and enter your credentials.

**PowerShell script won't run?**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Want detailed help?**
Read [AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md)

---

**Recommended:** Use GitHub Actions for hassle-free cloud automation! 🌟
