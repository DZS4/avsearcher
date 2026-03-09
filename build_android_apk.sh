#!/usr/bin/env bash
set -euo pipefail

: "${PYTHON:=python3}"

"$PYTHON" -m pip install -r requirements-native.txt
"$PYTHON" -m buildozer -v android debug
