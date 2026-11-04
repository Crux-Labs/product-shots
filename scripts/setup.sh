#!/usr/bin/env bash
# One-time setup: Python environment, demo product art, .env from the example, then a readiness report.
# Blender is separate (scripts/get_blender.sh) because it's a large download.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
  echo "Python 3.10 or newer is needed (found: $("$PY" --version 2>&1)). Install it, or set PYTHON=/path/to/python3." >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  [ -d .venv ] || uv venv -q --python "$PY" .venv
  uv pip install -q --python .venv/bin/python -e '.[dev]'
else
  [ -d .venv ] || "$PY" -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -e '.[dev]'
fi

.venv/bin/python examples/make_kits.py
[ -f .env ] || cp .env.example .env

.venv/bin/lf doctor || true
