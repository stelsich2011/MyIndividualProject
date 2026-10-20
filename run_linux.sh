#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
    echo 'Сначала установите приложение: python3 -m venv .venv'
    echo '.venv/bin/python -m pip install -e ".[desktop]"'
    exit 1
fi
exec .venv/bin/python -m oge_checker.desktop "$@"
