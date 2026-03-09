@echo off
setlocal

if "%PYTHON%"=="" set PYTHON=python

%PYTHON% -m pip install -r requirements-native.txt
%PYTHON% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name AVSearcher ^
  --add-data "avsearcher\\sources.json;avsearcher" ^
  main.py

echo.
echo Build finished. Output: dist\\AVSearcher\\AVSearcher.exe

