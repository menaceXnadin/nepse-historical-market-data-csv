@echo off
REM NEPSE Data Auto-Fetch and Push Script
REM This script runs the data fetcher and automatically commits/pushes to GitHub

echo ========================================
echo NEPSE Auto-Update Script
echo ========================================
echo.

REM Change to the script directory
cd /d "%~dp0"

echo [1/3] Running data fetch script...
echo.

REM Run the Python script
python asyncmain_incremental.py

REM Check if Python script ran successfully
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Python script failed!
    echo Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo [2/3] Checking for changes...
echo.

REM Check if there are changes to commit
git status --porcelain > nul
git diff --quiet
if %ERRORLEVEL% EQU 0 (
    echo No changes detected. Nothing to commit.
    echo.
    echo ========================================
    echo Script completed successfully!
    echo ========================================
    exit /b 0
)

echo Changes detected! Proceeding with commit and push...
echo.

echo [3/3] Committing and pushing to GitHub...
echo.

REM Add all changes
git add .

REM Commit with current date
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
git commit -m "Data update: %mydate%"

REM Push to GitHub
git push origin master

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Data updated and pushed to GitHub
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERROR: Failed to push to GitHub
    echo Please check your internet connection and Git credentials
    echo ========================================
    pause
    exit /b 1
)

echo.
exit /b 0
