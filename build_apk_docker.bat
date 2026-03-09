@echo off
REM ============================================================
REM  AVSearcher APK Builder  (Windows + Docker)
REM  需要安装 Docker Desktop 并确保 Docker 正在运行
REM ============================================================

echo [1/3] 构建 Docker 镜像（首次较慢，之后秒开）...
docker build -t avsearcher-builder -f Dockerfile.buildozer .
if errorlevel 1 (
    echo [ERROR] Docker 镜像构建失败，请确保 Docker Desktop 正在运行
    pause
    exit /b 1
)

echo [2/3] 在容器内编译 APK...
docker run --rm -v "%cd%\bin:/app/bin" avsearcher-builder
if errorlevel 1 (
    echo [ERROR] APK 编译失败
    pause
    exit /b 1
)

echo [3/3] 完成！APK 文件位于 bin\ 目录
dir bin\*.apk 2>nul
pause
