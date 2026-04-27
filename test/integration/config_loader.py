#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Load integration test config from config-custom.yaml (and config-base.yaml).

Values are used as defaults when CLI options are not provided. Mirrors the behavior of scripts/config.mjs and
scripts/integration-env.mjs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def _project_root() -> Path:
    """Project root (directory containing config-custom.yaml)."""
    return Path(__file__).resolve().parents[2]


def load_config() -> dict[str, Any]:
    """Load merged config from config-base.yaml and config-custom.yaml."""
    if yaml is None:
        return {}
    root = _project_root()
    base_path = root / "config-base.yaml"
    custom_path = root / "config-custom.yaml"

    config: dict[str, Any] = {}
    if base_path.exists():
        with open(base_path) as f:
            config = yaml.safe_load(f) or {}

    if custom_path.exists():
        with open(custom_path) as f:
            custom = yaml.safe_load(f) or {}
        _deep_merge(config, custom)

    return config


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base in-place (override wins)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def get_config_values() -> dict[str, str]:
    """Extract deployment-related values from config.

    Supports both flat config and env-based config (env: X, X: { deploymentName, ... }).
    """
    config = load_config()
    if not config:
        return {}

    # Support env-based config: env: dev, dev: { deploymentName, appName, ... }
    env = config.get("env")
    if env and env in config and isinstance(config[env], dict):
        block = config[env]
    else:
        block = config

    def get(key: str, default: str = "") -> str:
        val = block.get(key)
        return str(val).strip() if val is not None and val != "" else default

    return {
        "deployment": get("deploymentName", "prod"),
        "app_name": get("appName", "lisa"),
        "stage": get("deploymentStage", "prod"),
        "region": get("region", "us-west-2"),
        "profile": get("profile", "default"),
    }


def fetch_url_from_aws(kind: str) -> str:
    """Fetch API or ALB URL from AWS via integration-env.mjs.

    kind: "api" -> API Gateway URL, "alb" -> REST/ALB URL.
    Returns empty string on failure.
    """
    root = _project_root()
    cmd = ["node", "scripts/integration-env.mjs", "api-url" if kind == "api" else "alb-url"]
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout:
            url = result.stdout.strip()
            return url if url and url != "None" else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Intentionally ignore errors; function returns empty string on failure.
        return ""
