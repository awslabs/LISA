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

"""Sets the input parameters for lisa-sdk tests.

Note: pytest_addoption for --api, --url, etc. is in the root conftest.py because pytest parses command-line options
before loading subdirectory conftests.

When --api/--url are not provided, values are loaded from config-custom.yaml or fetched from AWS via
scripts/integration-env.mjs (same as run-integration-tests.sh).
"""

import logging
import os
import time
from collections.abc import Generator
from test.integration.config_loader import fetch_url_from_aws, get_config_values
from test.utils.integration_test_utils import get_management_key
from typing import Any

import boto3
import pytest
from lisapy import LisaApi, LisaLlm


def _resolve_option(pytestconfig: pytest.Config, opt: str, config_key: str) -> str:
    """Resolve option: CLI > config-custom.yaml > default."""
    val = pytestconfig.getoption(opt)
    if val:
        return val
    cfg = get_config_values()
    return cfg.get(config_key, "")


def _resolve_url_option(pytestconfig: pytest.Config, kind: str) -> str:
    """Resolve url/api: CLI > fetch from AWS via integration-env.mjs."""
    val = pytestconfig.getoption(kind)
    if val:
        return val
    # url=ALB/REST, api=API Gateway
    aws_kind = "alb" if kind == "url" else "api"
    return fetch_url_from_aws(aws_kind)


@pytest.fixture(scope="session")
def url(pytestconfig: pytest.Config) -> str:
    """Get the REST url (ALB).

    From --url, or config-custom.yaml + AWS.
    """
    val = _resolve_url_option(pytestconfig, "url")
    if not val:
        pytest.skip(
            "REST URL required. Provide --url, or ensure config-custom.yaml exists and "
            "LISA is deployed (scripts/integration-env.mjs alb-url fetches from AWS)."
        )
    return val


@pytest.fixture(scope="session")
def api(pytestconfig: pytest.Config) -> str:
    """Get the API Gateway url.

    From --api, or config-custom.yaml + AWS.
    """
    val = _resolve_url_option(pytestconfig, "api")
    if not val:
        pytest.skip(
            "API URL required. Provide --api, or ensure config-custom.yaml exists and "
            "LISA is deployed (scripts/integration-env.mjs api-url fetches from AWS)."
        )
    return val


@pytest.fixture(scope="session")
def headers(api_key: str) -> dict:
    return {"Api-Key": api_key, "Authorization": api_key}


@pytest.fixture(scope="session")
def verify(pytestconfig: pytest.Config) -> bool | Any:
    """Get the verify argument."""
    if pytestconfig.getoption("verify") == "false":
        return False
    elif pytestconfig.getoption("verify") == "true":
        return True
    else:
        return pytestconfig.getoption("verify")


@pytest.fixture(scope="session")
def api_key(pytestconfig: pytest.Config) -> str:
    """Get management key from Secrets Manager.

    Uses same multi-pattern lookup as RAG tests.
    """
    profile = _resolve_option(pytestconfig, "profile", "profile") or "default"
    deployment_name = _resolve_option(pytestconfig, "deployment", "deployment") or "app"
    stage = _resolve_option(pytestconfig, "stage", "stage") or "prod"
    region = _resolve_option(pytestconfig, "region", "region") or "us-west-2"
    # Use same session/profile as RAG tests (AWS_PROFILE may be set by integration conftest)
    if profile and profile != "default":
        os.environ.setdefault("AWS_PROFILE", profile)
    try:
        return get_management_key(
            deployment_name=deployment_name,
            region=region,
            deployment_stage=stage,
        )
    except Exception as e:
        print(f"Error retrieving secret: {str(e)}")
        raise


@pytest.fixture(scope="session")
def api_token(pytestconfig: pytest.Config, api_key: str) -> Generator:
    """Create a token item in DynamoDB with expiration if none is provided."""
    auth_token = pytestconfig.getoption("auth_token")
    if auth_token is not None:
        return
    profile = _resolve_option(pytestconfig, "profile", "profile") or "default"
    deployment_name = _resolve_option(pytestconfig, "deployment", "deployment") or "app"
    table_name = f"{deployment_name}-LISAApiTokenTable"
    try:
        dynamodb = boto3.Session(profile_name=profile).resource("dynamodb")
        table = dynamodb.Table(table_name)
        current_time = int(time.time())
        expiration_time = current_time + 3600  # 3600 seconds = 1 hour
        item = {"token": api_key, "tokenExpiration": expiration_time}
        logging.info(f"Creating auth token with expiration={expiration_time}")
        table.put_item(Item=item)
        logging.info("Auth token created")
        yield
        table.delete_item(Key={"token": api_key})
    except Exception as e:
        print(f"Error creating token: {str(e)}")
        raise


@pytest.fixture(scope="session")
def lisa_api(api: str, verify: bool | str, headers: dict) -> LisaApi:
    return LisaApi(url=api, verify=verify, headers=headers)


@pytest.fixture(scope="session")
def lisa_llm(url: str, verify: bool | str, headers: dict) -> LisaLlm:
    return LisaLlm(url=url, verify=verify, headers=headers)
