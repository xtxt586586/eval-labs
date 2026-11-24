#!/usr/bin/env bash
set -euo pipefail
export PYTHONUTF8=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v python3.12 >/dev/null || {
  echo "Python 3.12 is required (expected python3.12 on PATH)." >&2
  exit 1
}
command -v npm >/dev/null || {
  echo "Node.js 20+ and npm are required." >&2
  exit 1
}

if [[ ! -x .venv/bin/python ]]; then
  python3.12 -m venv .venv
fi
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python demo/run_demo.py
.venv/bin/python -m pytest backend/tests -q
