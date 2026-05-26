@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

title AlphaCore Institutional Git Engine

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%" || goto :fatal_cd

echo.
echo =====================================================================
echo          AlphaCore Institutional Git Engine (AIGE)
echo =====================================================================
echo   [Working Directory]  %CD%
echo   [Current Time]       %DATE% %TIME%
echo =====================================================================
echo.

:: 1. Verify Git Environment
where git >nul 2>&1
if errorlevel 1 (
    echo [FATAL] Git is not installed or not available in system PATH.
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
    goto :error_exit
)

echo [1/6] Config: Optimizing local Git configurations...
git config --local core.quotepath false
git config --local core.autocrlf true
git config --local core.safecrlf false
echo       - core.quotepath = false (Correct Chinese character display)
echo       - core.autocrlf = true   (Automatic CRLF line ending conversion)
echo       - core.safecrlf = false  (Silenced redundant CR/LF warnings)
echo.

echo [2/6] Network: Validating remote connection and authority...
git ls-remote --exit-code origin >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Remote origin is unreachable or authentication failed.
    choice /M "Do you want to continue committing locally without pushing?"
    if errorlevel 2 goto :error_exit
    set "SKIP_PUSH=1"
) else (
    echo       Remote connection verified successfully.
    set "SKIP_PUSH="
)
echo.

echo [3/6] Integrity: Scanning for large file protection (>50MB)...
python scratch\check_large_files.py
if errorlevel 1 (
    echo [WARNING] Local repository contains files larger than 50MB.
    echo           Pushing large files to GitHub may fail or violate size policies.
    choice /M "Are you sure you want to proceed with staging these files?"
    if errorlevel 2 goto :error_exit
) else (
    echo       No large binary files detected. Clean repository state.
)
echo.

echo [4/6] Status: Analyzing Git working tree and current branch...
git status --short --branch
for /f "delims=" %%b in ('git branch --show-current') do set "CURRENT_BRANCH=%%b"
echo.

if not defined SKIP_PUSH (
    echo [Sync] Checking remote synchronization status...
    git fetch origin >nul 2>&1
    git rev-parse --verify --quiet "@{u}" >nul 2>&1
    if errorlevel 1 (
        echo       [INFO] Current branch '!CURRENT_BRANCH!' has no upstream remote yet.
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
        echo       Branch status: ahead=!AHEAD_COUNT!, behind=!BEHIND_COUNT!
        if not "!BEHIND_COUNT!"=="0" (
            if "!AHEAD_COUNT!"=="0" (
                echo [INFO] Local branch is behind origin/!CURRENT_BRANCH!. Fast-forwarding...
                git pull --ff-only
                if errorlevel 1 goto :error_exit
            ) else (
                echo [FATAL] Local and remote branches have diverged.
                echo         Please resolve manually with 'git pull --rebase' before pushing.
                goto :error_exit
            )
        )
    )
)
echo.

set "HAS_CHANGES="
for /f "delims=" %%s in ('git status --porcelain') do (
    set "HAS_CHANGES=1"
)

if not defined HAS_CHANGES (
    echo [INFO] No local file modifications detected.
    if defined SKIP_PUSH (
        echo       No changes to commit, and network push is disabled.
        goto :success_end
    )
    echo       Staging skipped. Pushing any pending local commits...
    goto :push_only
)

echo [5/6] Prepare: Staging and Committing Changes
set "COMMIT_MSG="
set /p "COMMIT_MSG=Enter commit message (press Enter for default 'Update AlphaCore project'): "
if not defined COMMIT_MSG (
    set "COMMIT_MSG=Update AlphaCore project"
)

echo.
echo       Staging all changes...
git add -A
if errorlevel 1 goto :error_exit

echo       Committing changes locally...
git commit -m "!COMMIT_MSG!"
if errorlevel 1 goto :error_exit
echo.

:push_only
if defined SKIP_PUSH (
    echo [INFO] Network push skipped. Changes committed locally.
    goto :success_end
)

echo [6/6] Publish: Pushing local changes to remote repository...
git push
if errorlevel 1 (
    echo.
    echo [WARN] Default push failed. Trying to set upstream for branch '!CURRENT_BRANCH!'...
    git push -u origin !CURRENT_BRANCH!
    if errorlevel 1 goto :error_exit
)

:success_end
echo.
echo =====================================================================
echo   SUCCESS - AlphaCore project has been fully synchronized!
echo =====================================================================
git status --short --branch
goto :end

:fatal_cd
echo [FATAL] Cannot access project directory: %PROJECT_DIR%
goto :error_exit

:error_exit
echo.
echo =====================================================================
echo   FAILED - Synchronization terminated due to errors.
echo =====================================================================
exit /b 1

:end
echo.
pause
endlocal
