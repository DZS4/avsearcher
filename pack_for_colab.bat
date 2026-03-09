@echo off
chcp 65001 >nul
title AVSearcher - 打包项目用于 Colab 构建

echo ============================================
echo   AVSearcher 项目打包（用于 Colab 构建 APK）
echo ============================================
echo.

REM 检查 7z 或 tar
where tar >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 tar 命令
    pause
    exit /b 1
)

echo [步骤1] 打包项目文件...

REM 创建临时目录
if exist "_pack_temp" rmdir /s /q _pack_temp
mkdir _pack_temp\avsearcher_project

REM 复制必要文件
copy main.py _pack_temp\avsearcher_project\ >nul
copy buildozer.spec _pack_temp\avsearcher_project\ >nul
xcopy /s /e /i avsearcher _pack_temp\avsearcher_project\avsearcher >nul

REM 排除 __pycache__
for /d /r _pack_temp %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

REM 打包
cd _pack_temp
tar -czf ..\avsearcher_project.tar.gz avsearcher_project
cd ..

REM 清理
rmdir /s /q _pack_temp

echo [OK] 已生成 avsearcher_project.tar.gz
echo.
echo ============================================
echo   接下来请按以下步骤操作：
echo.
echo   1. 打开 Google Colab: https://colab.research.google.com/
echo   2. 新建笔记本
echo   3. 将下面的代码粘贴到第一个单元格中运行：
echo.
echo   ───── 代码开始 ─────
echo.
echo   # 第1步：上传并解压项目
echo   from google.colab import files
echo   uploaded = files.upload()  # 选择 avsearcher_project.tar.gz
echo   !tar -xzf avsearcher_project.tar.gz
echo   %%cd avsearcher_project
echo.
echo   ───── 粘贴到第二个单元格 ─────
echo.
echo   # 第2步：安装工具并构建APK（约需15-30分钟）
echo   !pip install -q buildozer==1.5.0 cython==0.29.36
echo   !sudo apt-get update -qq
echo   !sudo apt-get install -y -qq openjdk-17-jdk autoconf libtool pkg-config ^
echo       libffi-dev libssl-dev zlib1g-dev cmake ccache zip unzip
echo   !yes ^| buildozer -v android debug
echo.
echo   ───── 粘贴到第三个单元格 ─────
echo.
echo   # 第3步：下载APK
echo   import glob
echo   apks = glob.glob('bin/*.apk')
echo   if apks: files.download(apks[0])
echo   else: print("构建失败，请检查上方日志")
echo.
echo   ───── 代码结束 ─────
echo ============================================
echo.
pause
