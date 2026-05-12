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
  # litellm[proxy] pins orjson==3.10.15 (no cp314 wheel; source build breaks on PyO3). Install the
  # rest of requirements-dev, add litellm without deps, backfill proxy requirements except orjson,
  # then install a current orjson wheel only.
  TMP_REQ="$(mktemp)"
  trap 'rm -f "$TMP_REQ"' EXIT
  grep -v '^litellm' "$ROOT/requirements-dev.txt" >"$TMP_REQ"
  "$PY" -m pip install --prefer-binary -r "$TMP_REQ"
  "$PY" -m pip install --no-deps 'litellm[proxy]==1.83.7'
  LLM_REQS=()
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -n "$line" ]] && LLM_REQS+=("$line")
  done < <("$PY" "$ROOT/scripts/print_litellm_proxy_requirements.py")
  if ((${#LLM_REQS[@]} > 0)); then
    "$PY" -m pip install --prefer-binary "${LLM_REQS[@]}"
  fi
  "$PY" -m pip install --no-deps --force-reinstall --only-binary orjson 'orjson>=3.11.9'
else
  "$PY" -m pip install --prefer-binary -r requirements-dev.txt
fi
"$PY" -m pip install -e lisa-sdk
"$PY" -m pip install -e lib/serve/mcp-workbench
