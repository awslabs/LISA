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

"""Root conftest - registers pytest options needed by integration tests.

pytest_addoption() must be in a root-level conftest because pytest parses
command-line options before loading subdirectory conftests. Options used by
test/integration/sdk/ (--api, --url, etc.) must be registered here.
"""

from pytest import Parser


def pytest_addoption(parser: Parser) -> None:
    """Register CLI options for integration tests (e.g. test/integration/sdk/)."""
    parser.addoption(
        "--url",
        action="store",
        default=None,
        help="REST url used for testing. If not provided, read from config-custom.yaml or fetch from AWS.",
    )
    parser.addoption(
        "--api",
        action="store",
        default=None,
        help="API Gateway url used for testing. If not provided, read from config-custom.yaml or fetch from AWS.",
    )
    parser.addoption("--verify", action="store", default="false", help="Verify https request")
    parser.addoption(
        "--region",
        action="store",
        default=None,
        help="AWS region. Defaults to config-custom.yaml or us-west-2.",
    )
    parser.addoption(
        "--stage",
        action="store",
        default=None,
        help="Deployment stage. Defaults to config-custom.yaml or dev.",
    )
    parser.addoption(
        "--deployment",
        action="store",
        default=None,
        help="Deployment name. Defaults to config-custom.yaml or app.",
    )
    parser.addoption(
        "--profile",
        action="store",
        default=None,
        help="AWS profile. Defaults to config-custom.yaml or default.",
    )
    parser.addoption("--auth_token", action="store", default=None, help="Auth token for API tests")
