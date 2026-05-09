@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

title Touzi GitHub One-Click Push

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%" || goto :fatal_cd

echo.
echo ============================================================
echo   Touzi GitHub One-Click Push
echo ============================================================
echo   Project: %CD%
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo [FATAL] Git is not installed or not available in PATH.
    goto :error_exit
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [FATAL] Current directory is not a Git repository.
    goto :error_exit
)

for /f "delims=" %%u in ('git remote get-url origin 2^>nul') do set "ORIGIN_URL=%%u"
if not defined ORIGIN_URL (
    echo [FATAL] Git remote "origin" is not configured.
    echo         Run: git remote add origin https://github.com/terryzhoo-max/google-touzi.git
    goto :error_exit
)

echo [1/5] Remote
echo       origin = !ORIGIN_URL!
echo.

echo [2/5] Branch
git status --short --branch
if errorlevel 1 goto :error_exit
echo.

echo [3/5] Working tree
git status --short
if errorlevel 1 goto :error_exit
echo.

set "HAS_CHANGES="
for /f "delims=" %%s in ('git status --porcelain') do (
    set "HAS_CHANGES=1"
)

if not defined HAS_CHANGES (
    echo [INFO] No local file changes detected. Pushing any existing local commits...
    goto :push_only
)

set "COMMIT_MSG="
set /p "COMMIT_MSG=Commit message (press Enter for default): "
if not defined COMMIT_MSG (
    set "COMMIT_MSG=Update AlphaCore project"
)

echo.
echo [4/5] Staging all changes
git add -A
if errorlevel 1 goto :error_exit

echo.
echo [5/5] Commit
git commit -m "!COMMIT_MSG!"
if errorlevel 1 goto :error_exit

:push_only
echo.
echo [Push] Uploading to GitHub...
git push
if errorlevel 1 (
    echo.
    echo [WARN] Normal push failed. Trying to set upstream for current branch...
    for /f "delims=" %%b in ('git branch --show-current') do set "CURRENT_BRANCH=%%b"
    if not defined CURRENT_BRANCH (
        echo [FATAL] Cannot detect current branch.
        goto :error_exit
    )
    git push -u origin !CURRENT_BRANCH!
    if errorlevel 1 goto :error_exit
)

echo.
echo ============================================================
echo   SUCCESS - Local project has been pushed to GitHub.
echo ============================================================
git status --short --branch
goto :end

:fatal_cd
echo [FATAL] Cannot enter project directory: %PROJECT_DIR%
goto :error_exit

:error_exit
echo.
echo ============================================================
echo   FAILED - Check the error message above.
echo ============================================================
exit /b 1

:end
echo.
pause
endlocal
