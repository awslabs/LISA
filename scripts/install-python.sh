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

if "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 14) else 1)' 2>/dev/null; then
  echo "error: Python 3.14+ is not supported for LISA dev installs." >&2
  echo "LiteLLM >=1.86.2 (required for CVE-2026-49468) requires Python <3.14." >&2
  echo "Use Python 3.13 (e.g. pyenv local 3.13.x or python3.13 -m venv .venv)." >&2
  exit 1
fi

"$PY" -m pip install --prefer-binary -r requirements-dev.txt
"$PY" -m pip install -e lisa-sdk
"$PY" -m pip install -e lib/serve/mcp-workbench
