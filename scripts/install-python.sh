#!/usr/bin/env bash
# Install dev Python deps using the repo virtualenv when present so `npm run install:python`
# matches `source .venv/bin/activate` (same precedence as scripts/run-pytest.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
else
  PY="python3"
fi

"$PY" -m pip install --upgrade pip
"$PY" -m pip install --prefer-binary -r requirements-dev.txt
"$PY" -m pip install -e lisa-sdk
"$PY" -m pip install -e lib/serve/mcp-workbench
