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

"""Sets the input parameters for lisa-sdk tests."""

import logging
import time
from typing import Any, Generator, Union

import boto3
import pytest
from pytest import Parser

from lisapy import LisaApi, LisaLlm

def pytest_addoption(parser: Parser) -> None:
    """Set the options for the cli parser."""
    parser.addoption(
        "--url",
        action="store",
        help="REST url used for testing. This can be found as the output to lisa-serve CFN stack, e.g. "
        "https://app-rest-${account}.${region}.elb.amazonaws.com/${app_name}/",
    )
    parser.addoption(
        "--api",
        action="store",
        help="API Gateway url used for testing. This can be found as the output to lisa-serve CFN stack, e.g. "
        "https://${gateway-id}.execute-api.${region}.amazonaws.com/{stage}",
    )
    parser.addoption("--verify", action="store", default="false", help="Verify https request")
    parser.addoption("--region", action="store", default="us-west-2", help="Region for aws account")
    parser.addoption("--stage", action="store", default="dev", help="Deployment app name for LISA")
    parser.addoption("--deployment", action="store", default="app", help="Deployment app name for LISA")
    parser.addoption("--profile", action="store", default="default", help="AWS profile for account")


@pytest.fixture(scope="session")
def url(pytestconfig: pytest.Config) -> str:
    """Get the url argument."""
    url: str = pytestconfig.getoption("url")
    return url


@pytest.fixture(scope="session")
def api(pytestconfig: pytest.Config) -> str:
    """Get the api url argument."""
    api: str = pytestconfig.getoption("api")
    return api


@pytest.fixture(scope="session")
def headers(api_key: str) -> dict:
    return {"Api-Key": api_key, "Authorization": api_key}


@pytest.fixture(scope="session")
def verify(pytestconfig: pytest.Config) -> Union[bool, Any]:
    """Get the verify argument."""
    if pytestconfig.getoption("verify") == "false":
        return False
    elif pytestconfig.getoption("verify") == "true":
        return True
    else:
        return pytestconfig.getoption("verify")


@pytest.fixture(scope="session")
def api_key(pytestconfig: pytest.Config) -> str:
    try:
        profile = pytestconfig.getoption("profile")
        deployment_name = pytestconfig.getoption("deployment")
        secret_name = f"{deployment_name}-lisa-management-key"

        # Create a Secrets Manager client
        session = boto3.Session(profile_name=profile)
        client = session.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_name)
        key: str = response["SecretString"]
        return key
    except Exception as e:
        print(f"Error retrieving secret: {str(e)}")
        raise


@pytest.fixture(scope="session")
def api_token(pytestconfig: pytest.Config, api_key: str) -> Generator:
    """
    Create a token item in DynamoDB with expiration if none is provided
    """
    auth_token = pytestconfig.getoption("auth_token")
    if auth_token is not None:
        return
    profile = pytestconfig.getoption("profile")
    deployment_name = pytestconfig.getoption("deployment")
    table_name = f"{deployment_name}-LISAApiTokenTable"
    try:
        dynamodb = boto3.Session(profile_name=profile).resource("dynamodb")
        table = dynamodb.Table(table_name)
        current_time = int(time.time())
        expiration_time = current_time + 3600  # 3600 seconds = 1 hour
        item = {"token": api_key, "tokenExpiration": expiration_time}
        logging.info(f"Creating new auth token: {item}")
        table.put_item(Item=item)
        logging.info(f"Auth token created: {item}")
        yield
        table.delete_item(Key={"token": api_key})
    except Exception as e:
        print(f"Error creating token: {str(e)}")
        raise

@pytest.fixture(scope="session")
def lisa_api(api: str, verify: Union[bool, str], headers: dict) -> LisaApi:
    return LisaApi(api=api, verify=verify, headers=headers)

@pytest.fixture(scope="session")
def lisa_llm(url: str, verify: Union[bool, str], headers: dict) -> LisaLlm:
    return LisaLlm(url=url, verify=verify, headers=headers)
