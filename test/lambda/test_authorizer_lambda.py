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

import functools
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import call, MagicMock, patch

import boto3
import jwt
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["CLIENT_ID"] = "test-client-id"
os.environ["AUTHORITY"] = "https://test-authority"
os.environ["ADMIN_GROUP"] = "admin-group"
os.environ["JWT_GROUPS_PROP"] = "groups"
os.environ["TOKEN_TABLE_NAME"] = "token-table"
os.environ["MANAGEMENT_KEY_NAME"] = "test-management-key"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_authorization_wrapper(func):
    """Mock authorization wrapper for testing."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Just re-raise the exception for testing
            raise e

    return wrapper


# Create mock modules
mock_common = MagicMock()
mock_common.retry_config = retry_config
mock_common.authorization_wrapper = mock_authorization_wrapper

# Create mock create_env_variables
mock_create_env = MagicMock()

# Mock JWT module
mock_jwt = MagicMock()
mock_jwt.decode.return_value = {
    "sub": "test-user-id",
    "username": "test-user",
    "groups": ["test-group"],
}
mock_jwt.exceptions.PyJWTError = jwt.exceptions.PyJWTError

# First, patch sys.modules
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
    },
).start()

# Then patch the specific functions (but NOT get_id_token - that needs to work normally)
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.authorization_wrapper", mock_authorization_wrapper).start()

# Now import the lambda functions
from authorizer.lambda_functions import (
    find_jwt_username,
    generate_policy,
    get_management_tokens,
    id_token_is_valid,
    is_admin,
    is_valid_api_token,
    lambda_handler,
)


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def token_table(dynamodb):
    """Create a mock DynamoDB table for tokens."""
    table = dynamodb.create_table(
        TableName="token-table",
        KeySchema=[
            {"AttributeName": "token", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "token", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def sample_event():
    """Create a sample API Gateway event."""
    return {
        "resource": "/test-resource",
        "path": "/test-path",
        "httpMethod": "GET",
        "headers": {"Authorization": "Bearer test-token"},
        "multiValueHeaders": {},
        "queryStringParameters": {},
        "multiValueQueryStringParameters": {},
        "pathParameters": {},
        "stageVariables": {},
        "body": None,
        "isBase64Encoded": False,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abc123/test/GET/test-resource",
    }


@pytest.fixture
def sample_jwt_data():
    """Create a sample JWT data."""
    return {"sub": "test-user-id", "username": "test-user", "groups": ["test-group"], "nested": {"property": "value"}}


def test_generate_policy():
    """Test the generate_policy function."""
    # Test allow policy
    allow_policy = generate_policy(effect="Allow", resource="test-resource", username="test-user")
    assert allow_policy["principalId"] == "test-user"
    assert allow_policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    assert allow_policy["policyDocument"]["Statement"][0]["Resource"] == "test-resource"

    # Test deny policy
    deny_policy = generate_policy(effect="Deny", resource="test-resource")
    assert deny_policy["principalId"] == "username"  # Default value
    assert deny_policy["policyDocument"]["Statement"][0]["Effect"] == "Deny"
    assert deny_policy["policyDocument"]["Statement"][0]["Resource"] == "test-resource"


def test_find_jwt_username(sample_jwt_data):
    """Test the find_jwt_username function."""
    # Testing different JWT data scenarios to validate username extraction

    # Test with 'sub' field - this is used when 'cognito:username' is not present
    assert find_jwt_username(sample_jwt_data) == "test-user-id"

    # Test with 'cognito:username' field (which is prioritized over 'sub')
    data_with_cognito_username = {"cognito:username": "cognito-user", "sub": "sub-user"}
    assert find_jwt_username(data_with_cognito_username) == "cognito-user"

    # Test without any valid fields
    data_without_username_or_sub = {}
    with pytest.raises(ValueError) as excinfo:
        find_jwt_username(data_without_username_or_sub)
    assert "No username found in JWT" in str(excinfo.value)


def test_is_admin(sample_jwt_data):
    """Test the is_admin function."""
    # Test when user is admin
    sample_jwt_data["groups"] = ["test-group", "admin-group"]
    assert is_admin(sample_jwt_data, "admin-group", "groups") is True

    # Test when user is not admin
    sample_jwt_data["groups"] = ["test-group"]
    assert is_admin(sample_jwt_data, "admin-group", "groups") is False

    # Test when groups property doesn't exist
    del sample_jwt_data["groups"]
    assert is_admin(sample_jwt_data, "admin-group", "groups") is False


def test_is_valid_api_token(token_table):
    """Test the is_valid_api_token function."""
    import hashlib
    from datetime import datetime, timedelta

    # Patch the module-level token_table with our test fixture
    with patch("authorizer.lambda_functions.token_table", token_table):
        # Test with valid, non-expired token
        future_time = int((datetime.now() + timedelta(hours=1)).timestamp())
        valid_token = "valid-api-token"
        valid_token_hash = hashlib.sha256(valid_token.encode()).hexdigest()
        token_table.put_item(
            Item={
                "token": valid_token_hash,
                "tokenUUID": "test-uuid-123",
                "tokenExpiration": future_time,
                "username": "test-user",
                "groups": ["test-group"],
            }
        )
        result = is_valid_api_token(valid_token)
        assert result is not None
        assert result.get("tokenUUID") == "test-uuid-123"
        assert result.get("username") == "test-user"

        # Test with expired token
        past_time = int((datetime.now() - timedelta(hours=1)).timestamp())
        expired_token = "expired-api-token"
        expired_token_hash = hashlib.sha256(expired_token.encode()).hexdigest()
        token_table.put_item(
            Item={"token": expired_token_hash, "tokenUUID": "test-uuid-456", "tokenExpiration": past_time}
        )
        assert is_valid_api_token(expired_token) is None

        # Test with legacy token (no tokenUUID)
        legacy_token = "legacy-api-token"
        legacy_token_hash = hashlib.sha256(legacy_token.encode()).hexdigest()
        token_table.put_item(Item={"token": legacy_token_hash, "tokenExpiration": future_time})
        assert is_valid_api_token(legacy_token) is None

        # Test with non-existent token
        assert is_valid_api_token("non-existent-token") is None

        # Test with empty token
        assert is_valid_api_token("") is None

        # Test with None token
        assert is_valid_api_token(None) is None


def test_get_management_tokens():
    """Test the get_management_tokens function."""
    # Mock the get_secret_value response
    with patch("authorizer.lambda_functions.secrets_manager.get_secret_value") as mock_get_secret:
        # Setup mock to return current and previous tokens
        mock_current = MagicMock()
        mock_current.return_value = {"SecretString": "test-management-token-current"}
        mock_previous = MagicMock()
        mock_previous.return_value = {"SecretString": "test-management-token-previous"}

        # Use side_effect to return different values based on args
        def get_secret_side_effect(SecretId, VersionStage):
            if VersionStage == "AWSCURRENT":
                return {"SecretString": "test-management-token-current"}
            elif VersionStage == "AWSPREVIOUS":
                return {"SecretString": "test-management-token-previous"}
            else:
                raise ValueError(f"Unexpected VersionStage: {VersionStage}")

        mock_get_secret.side_effect = get_secret_side_effect

        # Clear the cache to ensure fresh execution
        get_management_tokens.cache_clear()

        # Test successful retrieval of tokens
        tokens = get_management_tokens()
        assert "test-management-token-current" in tokens
        assert "test-management-token-previous" in tokens

        # Verify the calls were made correctly
        mock_get_secret.assert_any_call(SecretId="test-management-key", VersionStage="AWSCURRENT")
        mock_get_secret.assert_any_call(SecretId="test-management-key", VersionStage="AWSPREVIOUS")

        # Reset for error test
        get_management_tokens.cache_clear()

        # Setup mock to raise exception for AWSCURRENT but succeed for AWSPREVIOUS
        def error_side_effect(SecretId, VersionStage):
            if VersionStage == "AWSCURRENT":
                raise ClientError(
                    {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}, "GetSecretValue"
                )
            else:
                raise ValueError("Should not be called")

        mock_get_secret.side_effect = error_side_effect

        # Test error handling
        tokens = get_management_tokens()
        assert tokens == []


@patch("authorizer.lambda_functions.requests.get")
@patch("authorizer.lambda_functions.jwt.PyJWKClient")
@patch("authorizer.lambda_functions.jwt.decode")
@patch("authorizer.lambda_functions.jwt.algorithms.has_crypto", True)
@patch("authorizer.lambda_functions.ssl.create_default_context")
@patch("authorizer.lambda_functions.os.getenv")
def test_id_token_is_valid(
    mock_getenv, mock_create_default_context, mock_jwt_decode, mock_PyJWKClient, mock_requests_get
):
    """Test the id_token_is_valid function."""
    # Mock the getenv return value for SSL_CERT_FILE
    mock_getenv.return_value = None

    # Mock the response from OIDC well-known endpoint
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jwks_uri": "https://test-authority/.well-known/jwks.json",
    }
    mock_requests_get.return_value = mock_response

    # Mock the SSL context
    mock_ctx = MagicMock()
    mock_create_default_context.return_value = mock_ctx

    # Mock the JWT client
    mock_jwks_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = "test-key"
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
    mock_PyJWKClient.return_value = mock_jwks_client

    # Mock the JWT decode return value
    jwt_data = {
        "sub": "test-user-id",
        "username": "test-user",
    }
    mock_jwt_decode.return_value = jwt_data

    # Test successful token validation
    result = id_token_is_valid(id_token="test-token", client_id="test-client-id", authority="https://test-authority")
    assert result == jwt_data

    # Test when OIDC metadata response is not 200
    mock_response.status_code = 404
    result = id_token_is_valid(id_token="test-token", client_id="test-client-id", authority="https://test-authority")
    assert result is None

    # Reset status code for the next test
    mock_response.status_code = 200

    # Test when JWT verification fails
    mock_jwt_decode.side_effect = jwt.exceptions.PyJWTError("Invalid token")
    result = id_token_is_valid(id_token="test-token", client_id="test-client-id", authority="https://test-authority")
    assert result is None

    # Test when has_crypto is False (using a with statement to isolate the patch)
    with patch("authorizer.lambda_functions.jwt.algorithms.has_crypto", False):
        result = id_token_is_valid(
            id_token="test-token", client_id="test-client-id", authority="https://test-authority"
        )
        assert result is None


@patch("authorizer.lambda_functions.get_management_tokens")
@patch("authorizer.lambda_functions.is_valid_api_token")
@patch("authorizer.lambda_functions.id_token_is_valid")
def test_lambda_handler_with_management_token(
    mock_id_token_is_valid, mock_is_valid_api_token, mock_get_management_tokens, sample_event, lambda_context
):
    """Test lambda_handler with management token."""
    # Mock the get_management_tokens to return our test token
    mock_get_management_tokens.return_value = ["test-token"]
    mock_is_valid_api_token.return_value = False

    # Test with management token
    response = lambda_handler(sample_event, lambda_context)

    # Verify response
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    assert response["principalId"] == "lisa-management-token"
    assert response["context"]["username"] == "lisa-management-token"
    assert json.loads(response["context"]["groups"]) == ["admin-group"]


@patch("authorizer.lambda_functions.get_management_tokens")
@patch("authorizer.lambda_functions.is_valid_api_token")
@patch("authorizer.lambda_functions.id_token_is_valid")
def test_lambda_handler_with_api_token(
    mock_id_token_is_valid, mock_is_valid_api_token, mock_get_management_tokens, sample_event, lambda_context
):
    """Test lambda_handler with API token."""
    # Mock to return empty management tokens but valid API token
    mock_get_management_tokens.return_value = []
    mock_is_valid_api_token.return_value = {"username": "api-token-user", "groups": ["api-group"]}

    # Test with API token
    response = lambda_handler(sample_event, lambda_context)

    # Verify response
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    assert response["principalId"] == "api-token-user"
    assert response["context"]["username"] == "api-token-user"
    assert json.loads(response["context"]["groups"]) == ["api-group"]


@patch("authorizer.lambda_functions.get_management_tokens")
@patch("authorizer.lambda_functions.is_valid_api_token")
@patch("authorizer.lambda_functions.id_token_is_valid")
@patch("authorizer.lambda_functions.is_admin")
@patch("authorizer.lambda_functions.find_jwt_username")
def test_lambda_handler_with_jwt(
    mock_find_jwt_username,
    mock_is_admin,
    mock_id_token_is_valid,
    mock_is_valid_api_token,
    mock_get_management_tokens,
    sample_event,
    lambda_context,
):
    """Test lambda_handler with JWT token."""
    # Mock to return valid JWT token
    mock_get_management_tokens.return_value = []
    mock_is_valid_api_token.return_value = False
    jwt_data = {
        "sub": "test-user-id",
        "username": "test-user",
        "groups": ["test-group"],
    }
    mock_id_token_is_valid.return_value = jwt_data
    mock_is_admin.return_value = False
    mock_find_jwt_username.return_value = "test-user"

    # Test with JWT token
    response = lambda_handler(sample_event, lambda_context)

    # Verify response
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    assert response["principalId"] == "test-user"
    assert response["context"]["username"] == "test-user"


@patch("authorizer.lambda_functions.get_management_tokens")
@patch("authorizer.lambda_functions.is_valid_api_token")
@patch("authorizer.lambda_functions.id_token_is_valid")
@patch("authorizer.lambda_functions.is_admin")
@patch("authorizer.lambda_functions.find_jwt_username")
def test_lambda_handler_admin_models_access(
    mock_find_jwt_username,
    mock_is_admin,
    mock_id_token_is_valid,
    mock_is_valid_api_token,
    mock_get_management_tokens,
    sample_event,
    lambda_context,
):
    """Test lambda_handler for admin access to models endpoint."""
    # Mock to return valid JWT token with admin access
    mock_get_management_tokens.return_value = []
    mock_is_valid_api_token.return_value = False
    jwt_data = {
        "sub": "test-user-id",
        "username": "test-user",
        "groups": ["admin-group"],
    }
    mock_id_token_is_valid.return_value = jwt_data
    mock_is_admin.return_value = True
    mock_find_jwt_username.return_value = "test-user"

    # Set up test event for models endpoint
    sample_event["resource"] = "/models/{modelId}"
    sample_event["path"] = "/models/specific-model"

    # Test with admin accessing models endpoint
    response = lambda_handler(sample_event, lambda_context)

    # Verify response
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Allow"


@patch("authorizer.lambda_functions.get_management_tokens")
@patch("authorizer.lambda_functions.is_valid_api_token")
@patch("authorizer.lambda_functions.id_token_is_valid")
@patch("authorizer.lambda_functions.is_admin")
@patch("authorizer.lambda_functions.find_jwt_username")
def test_lambda_handler_non_admin_models_access(
    mock_find_jwt_username,
    mock_is_admin,
    mock_id_token_is_valid,
    mock_is_valid_api_token,
    mock_get_management_tokens,
    sample_event,
    lambda_context,
):
    """Test lambda_handler for non-admin access to models endpoint."""
    # Mock to return valid JWT token without admin access
    mock_get_management_tokens.return_value = []
    mock_is_valid_api_token.return_value = False
    jwt_data = {
        "sub": "test-user-id",
        "username": "test-user",
        "groups": ["test-group"],
    }
    mock_id_token_is_valid.return_value = jwt_data
    mock_is_admin.return_value = False
    mock_find_jwt_username.return_value = "test-user"

    # Set up test event for models endpoint with specific model
    sample_event["resource"] = "/models/{modelId}"
    sample_event["path"] = "/models/specific-model"

    # Test with non-admin accessing specific model endpoint
    response = lambda_handler(sample_event, lambda_context)

    # Verify response - should be denied
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"

    # Set up test event for models list endpoint
    sample_event["resource"] = "/models"
    sample_event["path"] = "/models"

    # Test with non-admin accessing models list endpoint
    response = lambda_handler(sample_event, lambda_context)

    # Verify response - should be allowed for listing models
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Allow"


@patch("authorizer.lambda_functions.get_management_tokens")
@patch("authorizer.lambda_functions.is_valid_api_token")
@patch("authorizer.lambda_functions.id_token_is_valid")
@patch("authorizer.lambda_functions.is_admin")
@patch("authorizer.lambda_functions.find_jwt_username")
def test_lambda_handler_non_admin_configuration_update(
    mock_find_jwt_username,
    mock_is_admin,
    mock_id_token_is_valid,
    mock_is_valid_api_token,
    mock_get_management_tokens,
    sample_event,
    lambda_context,
):
    """Test lambda_handler for non-admin updating configuration."""
    # Mock to return valid JWT token without admin access
    mock_get_management_tokens.return_value = []
    mock_is_valid_api_token.return_value = False
    jwt_data = {
        "sub": "test-user-id",
        "username": "test-user",
        "groups": ["test-group"],
    }
    mock_id_token_is_valid.return_value = jwt_data
    mock_is_admin.return_value = False
    mock_find_jwt_username.return_value = "test-user"

    # Set up test event for configuration update
    sample_event["resource"] = "/configuration"
    sample_event["path"] = "/configuration"
    sample_event["httpMethod"] = "PUT"

    # Test with non-admin updating configuration
    response = lambda_handler(sample_event, lambda_context)

    # Verify response - should be denied
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"


@patch("authorizer.lambda_functions.get_management_tokens")
@patch("authorizer.lambda_functions.is_valid_api_token")
@patch("authorizer.lambda_functions.id_token_is_valid")
def test_lambda_handler_without_token(
    mock_id_token_is_valid, mock_is_valid_api_token, mock_get_management_tokens, sample_event, lambda_context
):
    """Test lambda_handler without a token."""
    # Mock to return valid JWT token without admin access
    mock_get_management_tokens.return_value = []
    mock_is_valid_api_token.return_value = False
    mock_id_token_is_valid.return_value = None

    # Remove token from request
    mock_common.get_id_token.return_value = None

    # Test without a token
    response = lambda_handler(sample_event, lambda_context)

    # Verify response - should be denied
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"

    # Reset mock for other tests
    mock_common.get_id_token.return_value = "test-token"


@patch("authorizer.lambda_functions.requests.get")
@patch("authorizer.lambda_functions.jwt.PyJWKClient")
@patch("authorizer.lambda_functions.jwt.decode")
@patch("authorizer.lambda_functions.jwt.algorithms.has_crypto", True)
@patch("authorizer.lambda_functions.ssl.create_default_context")
@patch("authorizer.lambda_functions.os.getenv")
def test_id_token_is_valid_with_cert_path(
    mock_getenv, mock_create_default_context, mock_jwt_decode, mock_PyJWKClient, mock_requests_get
):
    """Test the id_token_is_valid function with a certificate path."""
    # Configure the mock
    mock_context = MagicMock()
    mock_create_default_context.return_value = mock_context

    # Mock response from requests.get
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jwks_uri": "https://test-authority/jwks"}
    mock_requests_get.return_value = mock_response

    # Set up environment variable to provide a cert path
    mock_getenv.return_value = "/path/to/cert.pem"

    # Set up JWT decode
    mock_signing_key = MagicMock()
    mock_signing_key.key = "test-key"
    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
    mock_PyJWKClient.return_value = mock_jwks_client

    mock_jwt_decode.return_value = {"sub": "test-user-id"}

    # Call the function
    result = id_token_is_valid(id_token="test-token", client_id="test-client-id", authority="https://test-authority")

    # Assertions
    assert result == {"sub": "test-user-id"}
    # Verify cert_path was used to load verify locations
    mock_context.load_verify_locations.assert_called_once_with("/path/to/cert.pem")


def test_get_management_tokens_client_error():
    """Test the get_management_tokens function when ClientError is raised."""
    # Set up the ClientError to be raised
    error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}
    client_error = ClientError(error_response, "GetSecretValue")

    # We need to clear the cache since get_management_tokens uses @cache
    get_management_tokens.cache_clear()

    # Patch the secrets_manager global variable
    with patch("authorizer.lambda_functions.secrets_manager") as mock_secrets_manager:
        # Configure the mock to raise the ClientError
        mock_secrets_manager.get_secret_value.side_effect = client_error

        # Set environment variable with test management key name
        with patch("os.environ", {"MANAGEMENT_KEY_NAME": "test-management-key"}):
            # Call the function
            result = get_management_tokens()

            # Assertions
            assert result == []
            mock_secrets_manager.get_secret_value.assert_called_once_with(
                SecretId="test-management-key", VersionStage="AWSCURRENT"
            )


def test_generate_policy_default_username():
    """Test the generate_policy function with the default username."""
    # Test using the default username value
    policy = generate_policy(effect="Allow", resource="test-resource")

    # Check that default username 'username' is used
    assert policy["principalId"] == "username"

    # Check all policy details
    assert "policyDocument" in policy
    assert "Version" in policy["policyDocument"]
    assert policy["policyDocument"]["Version"] == "2012-10-17"
    assert "Statement" in policy["policyDocument"]

    # Ensure Statement is properly structured
    statement = policy["policyDocument"]["Statement"][0]
    assert "Action" in statement
    assert statement["Action"] == "execute-api:Invoke"
    assert "Effect" in statement
    assert statement["Effect"] == "Allow"
    assert "Resource" in statement
    assert statement["Resource"] == "test-resource"

    # Create an action trace to verify line coverage
    with patch("authorizer.lambda_functions.generate_policy", wraps=generate_policy) as wrapped_generate_policy:
        result = wrapped_generate_policy(effect="Deny", resource="another-resource")
        assert result["principalId"] == "username"
        assert result["policyDocument"]["Statement"][0]["Effect"] == "Deny"
        assert result["policyDocument"]["Statement"][0]["Resource"] == "another-resource"


def test_get_management_tokens_with_previous():
    """Test the get_management_tokens function retrieving both current and previous tokens."""
    # We need to clear the cache since get_management_tokens uses @cache
    get_management_tokens.cache_clear()

    # Patch the secrets_manager global variable
    with patch("authorizer.lambda_functions.secrets_manager") as mock_secrets_manager:
        # Configure mock to return different values for different calls
        mock_secrets_manager.get_secret_value.side_effect = [
            {"SecretString": "current-token"},  # First call - AWSCURRENT
            {"SecretString": "previous-token"},  # Second call - AWSPREVIOUS
        ]

        # Set environment variable with test management key name
        with patch("os.environ", {"MANAGEMENT_KEY_NAME": "test-management-key"}):
            # Call the function
            result = get_management_tokens()

            # Assertions
            assert result == ["current-token", "previous-token"]
            assert mock_secrets_manager.get_secret_value.call_count == 2

            # Check that both current and previous were called
            calls = [
                call(SecretId="test-management-key", VersionStage="AWSCURRENT"),
                call(SecretId="test-management-key", VersionStage="AWSPREVIOUS"),
            ]
            mock_secrets_manager.get_secret_value.assert_has_calls(calls, any_order=False)


def test_get_management_tokens_previous_exception():
    """Test the get_management_tokens function when the AWSPREVIOUS version raises an exception."""
    # We need to clear the cache since get_management_tokens uses @cache
    get_management_tokens.cache_clear()

    # Patch the secrets_manager global variable
    with patch("authorizer.lambda_functions.secrets_manager") as mock_secrets_manager:
        # Configure mock to return a value for AWSCURRENT but raise an exception for AWSPREVIOUS
        def side_effect(SecretId, VersionStage):
            if VersionStage == "AWSCURRENT":
                return {"SecretString": "current-token"}
            else:  # Must be AWSPREVIOUS
                raise Exception("No previous version exists")

        mock_secrets_manager.get_secret_value.side_effect = side_effect

        # Set environment variable with test management key name
        with patch("os.environ", {"MANAGEMENT_KEY_NAME": "test-management-key"}):
            # Call the function
            result = get_management_tokens()

            # Assertions
            assert result == ["current-token"]  # Only should have the current token
            assert mock_secrets_manager.get_secret_value.call_count == 2
