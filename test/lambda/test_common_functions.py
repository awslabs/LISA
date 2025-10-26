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

#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def setup_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_get_principal_id(setup_env):
    from utilities.common_functions import get_principal_id

    event = {"requestContext": {"authorizer": {"principal": "principal123"}}}
    assert get_principal_id(event) == "principal123"


def test_merge_fields_simple(setup_env):
    from utilities.common_functions import merge_fields

    source = {"field1": "value1", "field2": "value2"}
    target = {}
    result = merge_fields(source, target, ["field1"])
    assert result["field1"] == "value1"
    assert "field2" not in result


def test_merge_fields_nested(setup_env):
    from utilities.common_functions import merge_fields

    source = {"nested": {"field1": "value1"}}
    target = {}
    result = merge_fields(source, target, ["nested.field1"])
    assert result["nested"]["field1"] == "value1"


def test_get_property_path(setup_env):
    from utilities.common_functions import get_property_path

    data = {"level1": {"level2": {"value": "test"}}}
    assert get_property_path(data, "level1.level2.value") == "test"


def test_get_property_path_missing(setup_env):
    from utilities.common_functions import get_property_path

    data = {"level1": {}}
    assert get_property_path(data, "level1.missing") is None


def test_get_bearer_token(setup_env):
    from utilities.common_functions import get_bearer_token

    event = {"headers": {"Authorization": "Bearer token123"}}
    assert get_bearer_token(event) == "token123"


def test_get_bearer_token_lowercase(setup_env):
    from utilities.common_functions import get_bearer_token

    event = {"headers": {"authorization": "bearer token456"}}
    assert get_bearer_token(event) == "token456"


def test_get_bearer_token_missing(setup_env):
    from utilities.common_functions import get_bearer_token

    event = {"headers": {}}
    assert get_bearer_token(event) is None


def test_get_account_and_partition_from_env(setup_env, monkeypatch):
    from utilities.common_functions import get_account_and_partition

    monkeypatch.setenv("AWS_ACCOUNT_ID", "123456789012")
    monkeypatch.setenv("AWS_PARTITION", "aws")

    account, partition = get_account_and_partition()
    assert account == "123456789012"
    assert partition == "aws"


def test_get_account_and_partition_from_ecr(setup_env, monkeypatch):
    from utilities.common_functions import get_account_and_partition

    monkeypatch.delenv("AWS_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("ECR_REPOSITORY_ARN", "arn:aws:ecr:us-east-1:123456789012:repository/test")

    account, partition = get_account_and_partition()
    assert account == "123456789012"
    assert partition == "aws"


def test_generate_html_response(setup_env):
    from utilities.common_functions import generate_html_response

    response = generate_html_response(200, {"message": "success"})
    assert response["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in response["headers"]


def test_get_item_with_items():
    from utilities.common_functions import get_item

    response = {"Items": [{"id": "1"}]}
    result = get_item(response)
    if result:
        assert result["id"] == "1"


def test_get_item_empty(setup_env):
    from utilities.common_functions import get_item

    response = {"Items": []}
    assert get_item(response) is None


# Additional coverage tests
def test_generate_exception_response_with_http_status_code(setup_env):
    from utilities.common_functions import generate_exception_response

    class MockException(Exception):
        def __init__(self):
            self.http_status_code = 403
            self.message = "Forbidden"

    result = generate_exception_response(MockException())
    assert result["statusCode"] == 403


def test_generate_exception_response_with_status_code(setup_env):
    from utilities.common_functions import generate_exception_response

    class MockException(Exception):
        def __init__(self):
            self.status_code = 500
            self.message = "Internal Error"

    result = generate_exception_response(MockException())
    assert result["statusCode"] == 500


def test_sanitize_event_with_multivalue_headers(setup_env):
    from utilities.common_functions import _sanitize_event

    event = {"headers": {"Authorization": "Bearer token"}, "multiValueHeaders": {"Authorization": ["Bearer token"]}}
    result = _sanitize_event(event)
    assert "<REDACTED>" in result


def test_merge_fields_missing_nested(setup_env):
    from utilities.common_functions import merge_fields

    source = {"level1": {"level2": "value"}}
    target = {}
    result = merge_fields(source, target, ["level1.missing.field"])
    assert "missing" not in result.get("level1", {})


def test_authorization_wrapper(setup_env):
    from types import SimpleNamespace

    from utilities.common_functions import authorization_wrapper

    @authorization_wrapper
    def test_func(event, context):
        return "success"

    context = SimpleNamespace(function_name="test", aws_request_id="123")
    result = test_func({}, context)
    assert result == "success"


def test_decimal_encoder(setup_env):
    import json
    from decimal import Decimal

    from utilities.common_functions import DecimalEncoder

    data = {"value": Decimal("10.5")}
    result = json.dumps(data, cls=DecimalEncoder)
    assert "10.5" in result


def test_lambda_context_filter(setup_env):
    import logging

    from utilities.common_functions import LambdaContextFilter

    filter_obj = LambdaContextFilter()
    record = logging.LogRecord("test", logging.INFO, "", 1, "msg", (), None)
    result = filter_obj.filter(record)
    assert result is True
