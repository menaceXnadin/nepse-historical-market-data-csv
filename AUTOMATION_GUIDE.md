# NEPSE Data Automation Guide for Windows 11

This guide will help you automate the NEPSE data fetching and GitHub pushing process on Windows 11.

## 🎯 Quick Start

You have **3 automation options**:
1. **Windows Task Scheduler** (Recommended) - Runs automatically in the background
2. **Manual Script** - Double-click to run when needed
3. **GitHub Actions** - Cloud-based automation (no laptop needed!)

---

## 📋 Prerequisites

Before setting up automation, ensure:

1. ✅ Python is installed and `python` command works in terminal
2. ✅ Git is configured with your credentials
3. ✅ You can run `asyncmain_incremental.py` successfully
4. ✅ Git credentials are cached (so you don't need to enter password each time)

### Setting up Git Credentials (Important!)

To avoid password prompts, configure Git credential helper:

```powershell
# Store credentials permanently
git config --global credential.helper store

# Or use Windows Credential Manager (more secure)
git config --global credential.helper manager-core
```

After this, do one manual `git push` - enter your credentials, and they'll be saved.

---

## 🤖 Option 1: Windows Task Scheduler (Recommended)

This will run your script automatically every day at a specific time.

### Setup Steps:

1. **Open Task Scheduler**
   - Press `Win + R`
   - Type `taskschd.msc` and press Enter

2. **Create a New Task**
   - Click "Create Task" (not "Create Basic Task")
   - Name: `NEPSE Data Auto-Update`
   - Description: `Automatically fetch NEPSE data and push to GitHub`
   - ✅ Check "Run whether user is logged on or not"
   - ✅ Check "Run with highest privileges"
   - Configure for: `Windows 10/11`

3. **Set Triggers** (When to run)
   - Go to "Triggers" tab → Click "New"
   - Begin the task: `On a schedule`
   - Settings: `Daily`
   - Start: Choose your preferred time (e.g., `6:00 PM` after market closes)
   - ✅ Check "Enabled"
   - Click "OK"

4. **Set Actions** (What to run)
   - Go to "Actions" tab → Click "New"
   - Action: `Start a program`
   - Program/script: `powershell.exe`
   - Add arguments: `-ExecutionPolicy Bypass -File "C:\Users\MenaceXnadin\Documents\Machine Learning\NADIN NOTEBOOKS\NEPSE CSV\run_and_push.ps1"`
   - Start in: `C:\Users\MenaceXnadin\Documents\Machine Learning\NADIN NOTEBOOKS\NEPSE CSV`
   - Click "OK"

5. **Configure Settings**
   - Go to "Settings" tab
   - ✅ Check "Allow task to be run on demand"
   - ✅ Check "Run task as soon as possible after a scheduled start is missed"
   - ✅ Check "If the task fails, restart every: 10 minutes, 3 times"
   - Uncheck "Stop the task if it runs longer than: 3 days"
   - Change to: "Stop the task if it runs longer than: 1 hour"
   - Click "OK"

6. **Test the Task**
   - Right-click on your newly created task
   - Click "Run"
   - Check the "Last Run Result" column (should show "0x0" for success)

### Viewing Logs:

To see if the task ran successfully:
- Open Task Scheduler
- Find your task
- Check "Last Run Time" and "Last Run Result"
- Or check the "History" tab (enable it first via Action menu)

---

## 🖱️ Option 2: Manual Double-Click Scripts

If you prefer to run it manually when needed:

### Using Batch Script (Simple):
- Double-click `run_and_push.bat`
- A command window will open, run the script, and auto-close

### Using PowerShell Script (Better output):
- Right-click `run_and_push.ps1`
- Select "Run with PowerShell"

---

## ☁️ Option 3: GitHub Actions (Cloud Automation)

Run the script on GitHub's servers - no need for your laptop to be on!

### Setup Steps:

1. Create `.github/workflows/auto-update.yml` in your repository:

```yaml
name: Auto-Update NEPSE Data

on:
  schedule:
    # Runs every day at 12:00 PM UTC (5:45 PM Nepal Time)
    - cron: '0 12 * * *'
  workflow_dispatch:  # Allows manual trigger

jobs:
  update-data:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v3
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        
    - name: Run data fetch script
      run: |
        python asyncmain_incremental.py
        
    - name: Commit and push if changed
      run: |
        git config --global user.name 'github-actions[bot]'
        git config --global user.email 'github-actions[bot]@users.noreply.github.com'
        git add .
        git diff --quiet && git diff --staged --quiet || (git commit -m "Auto-update NEPSE data: $(date +'%Y-%m-%d %H:%M')" && git push)
```

2. Push this workflow file to your repository
3. GitHub will automatically run it daily!

### Advantages of GitHub Actions:
- ✅ No need for your laptop to be running
- ✅ Runs reliably in the cloud
- ✅ Free for public repositories
- ✅ Can see logs in GitHub Actions tab

---

## 🔍 Troubleshooting

### Script doesn't run in Task Scheduler:

**Check Python path:**
```powershell
where python
```
If it shows a path from Microsoft Store, install Python from python.org instead.

**Update the Task Scheduler action to use full Python path:**
- Program: `C:\Python310\python.exe` (use your actual Python path)
- Arguments: `"C:\Users\MenaceXnadin\Documents\Machine Learning\NADIN NOTEBOOKS\NEPSE CSV\asyncmain_incremental.py"`

### Git push asks for password:

```bash
# Use credential manager
git config --global credential.helper manager-core

# Or generate a Personal Access Token (PAT)
# GitHub → Settings → Developer settings → Personal access tokens
# Use the token as your password
```

### PowerShell script won't run (execution policy):

```powershell
# Run this as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Task runs but doesn't push to GitHub:

1. Check Git credentials are saved
2. Make sure you have internet connection
3. Run the script manually first to test
4. Check Task Scheduler history for error messages

---

## 📊 Monitoring Your Automation

### Check if it's working:

1. **GitHub commits**: Check your repository for daily commits
2. **Task Scheduler History**: View execution logs
3. **Create a log file**: Modify scripts to log to a file

### Adding Logging to PowerShell Script:

Add this at the beginning of `run_and_push.ps1`:
```powershell
$logFile = "$PSScriptRoot\automation.log"
Start-Transcript -Path $logFile -Append
```

Add this at the end:
```powershell
Stop-Transcript
```

Now check `automation.log` to see what happened during each run.

---

## 🎉 Recommended Setup

For the best experience on Windows 11:

1. ✅ Use **Windows Task Scheduler** with the **PowerShell script**
2. ✅ Schedule it for **6:00 PM daily** (after market closes)
3. ✅ Enable **logging** to track execution
4. ✅ Set up **Git credential manager** to avoid password prompts
5. ✅ Configure **email notifications** in Task Scheduler if you want alerts

---

## 💡 Tips

- The NEPSE market typically closes around 3 PM, so schedule updates for after 4-5 PM
- Test your automation on a weekend first
- Keep your Windows power settings to prevent sleep during scheduled tasks
- Consider using GitHub Actions if your laptop is often off

---

## 🆘 Need Help?

If you encounter issues:
1. Run the script manually first to ensure it works
2. Check the Task Scheduler history tab
3. Review the logs (if logging is enabled)
4. Make sure Git credentials are properly configured

---

**Happy Automating! 🚀**
