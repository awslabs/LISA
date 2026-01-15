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

import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

# Import after environment setup
# Import from specific modules (refactored structure)
from utilities.aws_helpers import (
    get_account_and_partition,
    get_cert_path,
    get_lambda_role_name,
    get_rest_api_container_endpoint,
)

# Import logging components from common_functions (still there)
from utilities.common_functions import LambdaContextFilter
from utilities.dict_helpers import get_item, get_property_path, merge_fields
from utilities.event_parser import get_bearer_token, get_id_token, get_principal_id, get_session_id
from utilities.lambda_decorators import api_wrapper, authorization_wrapper
from utilities.response_builder import DecimalEncoder, generate_exception_response, generate_html_response

# =====================
# Test LambdaContextFilter
# =====================


def test_lambda_context_filter_with_context():
    """Test LambdaContextFilter with valid context."""
    from utilities.lambda_decorators import ctx_context

    # Create a mock context
    mock_context = SimpleNamespace(aws_request_id="test-request-id", function_name="test-function")
    ctx_context.set(mock_context)

    # Create filter and log record
    filter = LambdaContextFilter()
    record = MagicMock()

    result = filter.filter(record)

    assert result is True
    assert record.requestid == "test-request-id"
    assert record.functionname == "test-function"


def test_lambda_context_filter_without_context():
    """Test LambdaContextFilter when context is missing."""
    from unittest.mock import patch

    # Create filter and log record
    filter = LambdaContextFilter()
    record = MagicMock()

    # Mock the ctx_context module-level import to raise LookupError
    with patch("utilities.common_functions.ctx_context") as mock_ctx:
        mock_ctx.get.side_effect = LookupError("No context")

        result = filter.filter(record)

        assert result is True
        assert record.requestid == "RID-MISSING"
        assert record.functionname == "FN-MISSING"

        assert result is True
        assert record.requestid == "RID-MISSING"
        assert record.functionname == "FN-MISSING"


# =====================
# Test DecimalEncoder
# =====================


def test_decimal_encoder_with_decimal():
    """Test DecimalEncoder handles Decimal objects."""
    obj = {"value": Decimal("123.45")}
    result = json.dumps(obj, cls=DecimalEncoder)
    assert '"value": 123.45' in result


def test_decimal_encoder_with_datetime():
    """Test DecimalEncoder handles datetime objects."""
    dt = datetime(2025, 1, 1, 12, 0, 0)
    obj = {"timestamp": dt}
    result = json.dumps(obj, cls=DecimalEncoder)
    assert "2025-01-01T12:00:00" in result


# =====================
# Test generate_html_response
# =====================


def test_generate_html_response():
    """Test generate_html_response creates proper response."""
    response = generate_html_response(200, {"message": "success"})

    assert response["statusCode"] == 200
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
    assert response["headers"]["Content-Type"] == "application/json"
    assert "message" in response["body"]


# =====================
# Test generate_exception_response
# =====================


def test_generate_exception_response_validation_error():
    """Test generate_exception_response with ValidationError."""

    class ValidationError(Exception):
        pass

    error = ValidationError("Validation failed")
    response = generate_exception_response(error)

    assert response["statusCode"] == 400
    assert "Validation failed" in response["body"]


def test_generate_exception_response_with_response_metadata():
    """Test generate_exception_response with AWS API error."""
    error = Exception("AWS Error")
    error.response = {"ResponseMetadata": {"HTTPStatusCode": 403}}  # type: ignore

    response = generate_exception_response(error)

    assert response["statusCode"] == 403


def test_generate_exception_response_with_http_status_code():
    """Test generate_exception_response with http_status_code attribute."""
    error = Exception("Custom error")
    error.http_status_code = 404  # type: ignore
    error.message = "Not found"  # type: ignore

    response = generate_exception_response(error)

    assert response["statusCode"] == 404
    assert "Not found" in response["body"]


def test_generate_exception_response_with_status_code():
    """Test generate_exception_response with status_code attribute."""
    error = Exception("Another error")
    error.status_code = 500  # type: ignore
    error.message = "Internal error"  # type: ignore

    response = generate_exception_response(error)

    assert response["statusCode"] == 500
    assert "Internal error" in response["body"]


def test_generate_exception_response_missing_request_context():
    """Test generate_exception_response with missing requestContext."""
    error = KeyError("requestContext")

    response = generate_exception_response(error)

    assert response["statusCode"] == 400
    # The error message will be wrapped in quotes, so check for the parameter name
    assert "requestContext" in response["body"]


def test_generate_exception_response_generic():
    """Test generate_exception_response with generic error."""
    error = Exception("Generic error message")

    response = generate_exception_response(error)

    assert response["statusCode"] == 500
    assert "An unexpected error occurred" in response["body"]


# =====================
# Test get_id_token
# =====================


def test_get_id_token_lowercase_authorization():
    """Test get_id_token with lowercase authorization header."""
    test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    event = {"headers": {"authorization": f"Bearer {test_token}"}}

    token = get_id_token(event)

    assert token == test_token


def test_get_id_token_uppercase_authorization():
    """Test get_id_token with uppercase Authorization header."""
    test_token = "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
    event = {"headers": {"Authorization": f"Bearer {test_token}"}}

    token = get_id_token(event)

    assert token == test_token


def test_get_id_token_lowercase_bearer():
    """Test get_id_token with lowercase bearer."""
    test_token = "dGVzdC10b2tlbi1mb3ItYXV0aGVudGljYXRpb24"
    event = {"headers": {"authorization": f"bearer {test_token}"}}

    token = get_id_token(event)

    assert token == test_token


def test_get_id_token_missing_header():
    """Test get_id_token when authorization header is missing."""
    event = {"headers": {}}

    with pytest.raises(ValueError):
        get_id_token(event)

    # Verify the error message
    try:
        get_id_token(event)
    except ValueError as e:
        assert "Missing authorization token" in str(e)


# =====================
# Test api_wrapper
# =====================


def test_api_wrapper_success():
    """Test api_wrapper with successful function execution."""

    @api_wrapper
    def test_function(event, context):
        return {"result": "success"}

    mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
    event = {"headers": {}, "httpMethod": "GET", "path": "/test"}

    response = test_function(event, mock_context)

    assert response["statusCode"] == 200
    assert "success" in response["body"]


def test_api_wrapper_exception():
    """Test api_wrapper handles exceptions."""

    @api_wrapper
    def test_function(event, context):
        raise ValueError("Test error")

    mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
    event = {"headers": {}, "httpMethod": "GET", "path": "/test"}

    response = test_function(event, mock_context)

    assert response["statusCode"] == 500
    assert "An unexpected error occurred" in response["body"]


# =====================
# Test authorization_wrapper
# =====================


def test_authorization_wrapper():
    """Test authorization_wrapper passes through result."""

    @authorization_wrapper
    def test_function(event, context):
        return {"authorized": True}

    mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
    event = {"headers": {}}

    result = test_function(event, mock_context)

    assert result == {"authorized": True}


# =====================
# Test get_cert_path
# =====================


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": ""})
def test_get_cert_path_no_arn():
    """Test get_cert_path when no ARN is specified."""
    mock_iam = MagicMock()

    # Clear cache
    get_cert_path.cache_clear()

    result = get_cert_path(mock_iam)

    assert result is True


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:acm:us-east-1:123456789012:certificate/abc-123"})
def test_get_cert_path_acm_certificate():
    """Test get_cert_path with ACM certificate."""
    mock_iam = MagicMock()

    # Clear cache
    get_cert_path.cache_clear()

    result = get_cert_path(mock_iam)

    assert result is True


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/test-cert"})
def test_get_cert_path_iam_certificate():
    """Test get_cert_path with IAM certificate."""
    mock_iam = MagicMock()
    mock_iam.get_server_certificate.return_value = {
        "ServerCertificate": {"CertificateBody": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"}
    }

    # Clear cache
    get_cert_path.cache_clear()

    result = get_cert_path(mock_iam)

    assert isinstance(result, str)
    assert result != ""
    mock_iam.get_server_certificate.assert_called_once_with(ServerCertificateName="test-cert")


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/test-cert"})
def test_get_cert_path_iam_error():
    """Test get_cert_path falls back when IAM call fails."""
    mock_iam = MagicMock()
    mock_iam.get_server_certificate.side_effect = Exception("IAM error")

    # Clear cache
    get_cert_path.cache_clear()

    result = get_cert_path(mock_iam)

    assert result is True


# =====================
# Test get_rest_api_container_endpoint
# =====================


@patch("utilities.aws_helpers.ssm_client")
@patch.dict(os.environ, {"LISA_API_URL_PS_NAME": "/lisa/api/url", "REST_API_VERSION": "v2"})
def test_get_rest_api_container_endpoint(mock_ssm):
    """Test get_rest_api_container_endpoint retrieves endpoint from SSM."""
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://api.example.com"}}

    # Clear cache
    get_rest_api_container_endpoint.cache_clear()

    result = get_rest_api_container_endpoint()

    assert result == "https://api.example.com/v2/serve"
    mock_ssm.get_parameter.assert_called_once_with(Name="/lisa/api/url")


# =====================
# Test get_session_id
# =====================


def test_get_session_id():
    """Test get_session_id extracts session ID from event."""
    event = {"pathParameters": {"sessionId": "session-123"}}

    session_id = get_session_id(event)

    assert session_id == "session-123"


def test_get_session_id_missing():
    """Test get_session_id when session ID is missing."""
    event = {"pathParameters": {}}

    session_id = get_session_id(event)

    assert session_id is None


# =====================
# Test get_principal_id
# =====================


def test_get_principal_id():
    """Test get_principal_id extracts principal from event."""
    event = {"requestContext": {"authorizer": {"principal": "user-123"}}}

    principal = get_principal_id(event)

    assert principal == "user-123"


def test_get_principal_id_missing():
    """Test get_principal_id when principal is missing."""
    event = {"requestContext": {}}

    principal = get_principal_id(event)

    assert principal == ""


# =====================
# Test merge_fields
# =====================


def test_merge_fields_top_level():
    """Test merge_fields with top-level fields."""
    source = {"field1": "value1", "field2": "value2", "field3": "value3"}
    target = {"existing": "data"}
    fields = ["field1", "field2"]

    result = merge_fields(source, target, fields)

    assert result["field1"] == "value1"
    assert result["field2"] == "value2"
    assert "field3" not in result
    assert result["existing"] == "data"


def test_merge_fields_nested():
    """Test merge_fields with nested fields."""
    source = {"nested": {"level1": {"level2": "value"}}}
    target = {}
    fields = ["nested.level1.level2"]

    result = merge_fields(source, target, fields)

    assert result["nested"]["level1"]["level2"] == "value"


def test_merge_fields_missing_source():
    """Test merge_fields when source field doesn't exist."""
    source = {"field1": "value1"}
    target = {}
    fields = ["field1", "field2"]

    result = merge_fields(source, target, fields)

    assert result["field1"] == "value1"
    assert "field2" not in result


def test_merge_fields_nested_missing():
    """Test merge_fields with missing nested fields."""
    source = {"nested": {"level1": "value"}}
    target = {}
    fields = ["nested.level1.missing"]

    result = merge_fields(source, target, fields)

    # Should not create the nested structure if source doesn't have it
    assert result == {}


# =====================
# Test get_lambda_role_name
# =====================


@patch("utilities.aws_helpers.boto3.client")
def test_get_lambda_role_name(mock_boto_client):
    """Test get_lambda_role_name extracts role name from ARN."""
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:sts::123456789012:assumed-role/MyLambdaRole/lambda-function"
    }
    mock_boto_client.return_value = mock_sts

    role_name = get_lambda_role_name()

    assert role_name == "MyLambdaRole"


# =====================
# Test get_item
# =====================


def test_get_item_with_items():
    """Test get_item returns first item."""
    response = {"Items": [{"id": "1"}, {"id": "2"}]}

    result = get_item(response)

    assert result == {"id": "1"}


def test_get_item_no_items():
    """Test get_item returns None when no items."""
    response = {"Items": []}

    result = get_item(response)

    assert result is None


def test_get_item_no_items_key():
    """Test get_item returns None when Items key missing."""
    response = {}

    result = get_item(response)

    assert result is None


# =====================
# Test get_property_path
# =====================


def test_get_property_path_simple():
    """Test get_property_path with simple path."""
    data = {"key": "value"}

    result = get_property_path(data, "key")

    assert result == "value"


def test_get_property_path_nested():
    """Test get_property_path with nested path."""
    data = {"level1": {"level2": {"level3": "value"}}}

    result = get_property_path(data, "level1.level2.level3")

    assert result == "value"


def test_get_property_path_missing():
    """Test get_property_path returns None for missing path."""
    data = {"key": "value"}

    result = get_property_path(data, "missing.path")

    assert result is None


# =====================
# Test get_bearer_token
# =====================


def test_get_bearer_token_uppercase():
    """Test get_bearer_token with uppercase Authorization header."""
    event = {"headers": {"Authorization": "Bearer test-token-123"}}

    token = get_bearer_token(event)

    assert token == "test-token-123"


def test_get_bearer_token_lowercase():
    """Test get_bearer_token with lowercase authorization header."""
    event = {"headers": {"authorization": "Bearer test-token-456"}}

    token = get_bearer_token(event)

    assert token == "test-token-456"


def test_get_bearer_token_missing():
    """Test get_bearer_token returns None when header missing."""
    event = {"headers": {}}

    token = get_bearer_token(event)

    assert token is None


def test_get_bearer_token_not_bearer():
    """Test get_bearer_token returns None when not Bearer format."""
    event = {"headers": {"Authorization": "Basic dXNlcjpwYXNz"}}

    token = get_bearer_token(event)

    assert token is None


# =====================
# Test get_account_and_partition
# =====================


@patch.dict(os.environ, {"AWS_ACCOUNT_ID": "123456789012", "AWS_PARTITION": "aws"})
def test_get_account_and_partition_from_env():
    """Test get_account_and_partition from environment variables."""
    account, partition = get_account_and_partition()

    assert account == "123456789012"
    assert partition == "aws"


@patch.dict(
    os.environ, {"ECR_REPOSITORY_ARN": "arn:aws-us-gov:ecr:us-gov-west-1:987654321098:repository/my-repo"}, clear=True
)
def test_get_account_and_partition_from_ecr_arn():
    """Test get_account_and_partition from ECR ARN."""
    os.environ["AWS_REGION"] = "us-gov-west-1"

    account, partition = get_account_and_partition()

    assert account == "987654321098"
    assert partition == "aws-us-gov"


@patch.dict(os.environ, {}, clear=True)
def test_get_account_and_partition_defaults():
    """Test get_account_and_partition with default values."""
    os.environ["AWS_REGION"] = "us-east-1"

    account, partition = get_account_and_partition()

    assert account == ""
    assert partition == "aws"
