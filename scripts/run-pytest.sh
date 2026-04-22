#!/usr/bin/env bash
# Run pytest with the repo virtualenv when present so `npm run test:*` matches
# `source .venv/bin/activate` (CI uses setup-python + pip install, so python3 works).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON:-}" ]]; then
    exec "$PYTHON" -m pytest "$@"
elif [[ -x "${ROOT}/.venv/bin/python" ]]; then
    exec "${ROOT}/.venv/bin/python" -m pytest "$@"
else
    exec python3 -m pytest "$@"
fi
