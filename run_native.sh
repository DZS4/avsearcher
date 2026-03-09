#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/.deps"
export KIVY_HOME="$(pwd)/.kivy-home"
export KIVY_NO_MTDEV=1

python3 main.py
