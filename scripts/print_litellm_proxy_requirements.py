#!/usr/bin/env python3
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

"""Emit PEP 508 requirement strings for litellm's [proxy] extra (for pip install), excluding orjson.

Used on Python 3.14+: litellm pins orjson==3.10.15 for [proxy], which has no cp314 wheel. Caller
installs litellm with --no-deps, runs this script, pip-installs the output, then installs orjson
from a wheel separately.
"""

from __future__ import annotations

import importlib
import importlib.metadata as m
import sys
from collections.abc import Callable
from typing import Any


def _packaging() -> tuple[Any, Callable[[], Any]]:
    """Load Requirement and default_environment from pip's vendor tree or the standalone package."""
    for prefix in ("pip._vendor.packaging", "packaging"):
        try:
            req_mod = importlib.import_module(f"{prefix}.requirements")
            mark_mod = importlib.import_module(f"{prefix}.markers")
        except ImportError:
            continue
        return req_mod.Requirement, mark_mod.default_environment
    raise ImportError(
        "packaging is required (bundled with pip or install the 'packaging' package)",
    )


def main() -> None:
    Requirement, default_environment = _packaging()
    try:
        dist = m.distribution("litellm")
    except m.PackageNotFoundError:
        print("error: litellm is not installed; install litellm[proxy] with --no-deps first", file=sys.stderr)
        sys.exit(1)
    env_proxy = default_environment()
    env_proxy["extra"] = "proxy"
    for raw in dist.requires or []:
        req = Requirement(raw)
        if req.name.lower() == "orjson":
            continue
        if req.marker is None:
            print(req)
        elif req.marker.evaluate(env_proxy):
            print(req)


if __name__ == "__main__":
    main()
