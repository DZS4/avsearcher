@echo off
chcp 65001 >nul
title AVSearcher - Push to GitHub and Build APK

echo ============================================
echo   AVSearcher APK Build (via GitHub Actions)
echo ============================================
echo.

REM 检查 git
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git not found. Install from https://git-scm.com/
    pause
    exit /b 1
)

REM 添加安全目录
git config --global --add safe.directory %CD%

REM 检查是否已初始化 git
if not exist ".git" (
    echo [Step 1] Init Git repo...
    git init
    git branch -M main
)

REM 检查 remote
git remote get-url origin >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [IMPORTANT] Please create a new repo on GitHub first.
    echo Example: https://github.com/YourUsername/avsearcher.git
    echo.
    set /p REPO_URL="Enter GitHub repo URL: "
    git remote add origin %REPO_URL%
) else (
    echo [OK] Git remote already set
)

REM 确保分支名为 main
git branch -M main

REM 检查是否有 .gitignore
if not exist ".gitignore" (
    echo [Step 2] Creating .gitignore...
    (
        echo dist/
        echo build/
        echo .buildozer/
        echo __pycache__/
        echo *.pyc
        echo *.pyo
        echo .venv/
        echo .android-home/
        echo .cache/
        echo .local/
        echo .local-debs/
        echo .local-jdk/
        echo .sysroot/
        echo .sysroot-bin/
    ) > .gitignore
)

echo.
echo [Step 3] Committing code...
git add -A
git commit -m "build: update for APK build"

echo.
echo [Step 4] Pushing to GitHub...
git push -u origin main

echo.
echo ============================================
echo   Done! GitHub Actions will build the APK.
echo.
echo   Check build status:
echo   Open your GitHub repo - Actions tab
echo.
echo   Download APK:
echo   Actions - Latest run - Artifacts - AVSearcher-APK
echo ============================================
echo.
pause
