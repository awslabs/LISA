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

"""Integration test conftest - sets env vars from config-custom.yaml when not already set.

RAG tests use LISA_API_URL, LISA_DEPLOYMENT_NAME, etc. When these are unset,
we load from config-custom.yaml and fetch URLs from AWS (via integration-env.mjs)
so that `npm run test:rag-integ` works without manually exporting env vars.
"""

import os
from test.integration.config_loader import fetch_url_from_aws, get_config_values

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Set RAG test env vars from config-custom.yaml when not already set."""
    if os.environ.get("LISA_API_URL"):
        return  # Already configured
    cfg = get_config_values()
    if not cfg:
        return
    api_url = fetch_url_from_aws("api")  # RAG uses API Gateway (repositories, collections)
    if not api_url:
        return
    os.environ.setdefault("LISA_API_URL", api_url)
    os.environ.setdefault("LISA_DEPLOYMENT_NAME", cfg.get("deployment", "app"))
    os.environ.setdefault("LISA_DEPLOYMENT_STAGE", cfg.get("stage", "dev"))
    os.environ.setdefault("AWS_DEFAULT_REGION", cfg.get("region", "us-west-2"))
    # Dev deployments often use self-signed certs
    os.environ.setdefault("LISA_VERIFY_SSL", "false")
    if cfg.get("profile"):
        os.environ.setdefault("AWS_PROFILE", cfg["profile"])
