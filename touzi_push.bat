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
for /f "delims=" %%b in ('git branch --show-current') do set "CURRENT_BRANCH=%%b"
if not defined CURRENT_BRANCH (
    echo [FATAL] Cannot detect current branch.
    goto :error_exit
)
echo.

echo [Sync] Checking remote branch state
git fetch origin
if errorlevel 1 goto :error_exit

git rev-parse --verify --quiet "@{u}" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Current branch has no upstream yet. It will be created during push.
) else (
    set "SYNC_COUNTS_FILE=%TEMP%\touzi_git_sync_counts_%RANDOM%.txt"
    git rev-list --left-right --count "@{u}...HEAD" > "!SYNC_COUNTS_FILE!"
    if errorlevel 1 goto :error_exit
    set /p SYNC_COUNTS=<"!SYNC_COUNTS_FILE!"
    del "!SYNC_COUNTS_FILE!" >nul 2>&1
    for /f "tokens=1,2" %%a in ("!SYNC_COUNTS!") do (
        set "BEHIND_COUNT=%%a"
        set "AHEAD_COUNT=%%b"
    )
    echo       ahead=!AHEAD_COUNT! behind=!BEHIND_COUNT!
    if not "!BEHIND_COUNT!"=="0" (
        if "!AHEAD_COUNT!"=="0" (
            echo [INFO] Local branch is behind upstream. Fast-forwarding before push...
            git pull --ff-only
            if errorlevel 1 goto :error_exit
        ) else (
            echo [FATAL] Local and remote branches have diverged.
            echo         This script will not auto-commit or push a diverged branch.
            echo         Resolve manually with one of:
            echo           git pull --rebase
            echo           git merge origin/!CURRENT_BRANCH!
            echo         Then rerun this script after conflicts are resolved.
            goto :error_exit
        )
    )
)

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
