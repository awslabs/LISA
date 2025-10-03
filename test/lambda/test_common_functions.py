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

"""
Refactored common functions tests using fixture-based mocking instead of global mocks.
This replaces the original test_common_functions.py with isolated, maintainable tests.
"""

import json
import os
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from conftest import LambdaTestHelper


# Set up test environment variables
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing", 
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    yield
    
    # Cleanup
    for key in env_vars.keys():
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def mock_common_functions():
    """Mock common functions module imports."""
    with patch('utilities.common_functions.logging') as mock_logging:
        mock_logging.getLogger.return_value = MagicMock()
        yield {
            'logging': mock_logging
        }


@pytest.fixture
def common_functions():
    """Import common functions module."""
    from utilities import common_functions
    return common_functions


@pytest.fixture
def validation_module():
    """Import validation module."""
    from utilities import validation
    return validation


@pytest.fixture
def validators_module():
    """Import validators module."""
    from utilities import validators
    return validators


class TestGetPropertyPath:
    """Test get_property_path function - REFACTORED VERSION."""
    
    def test_get_property_path_simple_property(self, sample_jwt_data, common_functions):
        """Test get_property_path with simple property."""
        result = common_functions.get_property_path(sample_jwt_data, "username")
        assert result == "test-user"

    def test_get_property_path_nested_property(self, sample_jwt_data, common_functions):
        """Test get_property_path with nested property."""
        result = common_functions.get_property_path(sample_jwt_data, "nested.property")
        assert result == "value"

    def test_get_property_path_non_existent(self, sample_jwt_data, common_functions):
        """Test get_property_path with non-existent property."""
        result = common_functions.get_property_path(sample_jwt_data, "nonexistent")
        assert result is None

    def test_get_property_path_non_existent_nested(self, sample_jwt_data, common_functions):
        """Test get_property_path with non-existent nested property."""
        result = common_functions.get_property_path(sample_jwt_data, "nested.nonexistent")
        assert result is None

    def test_get_property_path_non_existent_parent(self, sample_jwt_data, common_functions):
        """Test get_property_path with non-existent parent."""
        result = common_functions.get_property_path(sample_jwt_data, "nonexistent.property")
        assert result is None


class TestDecimalEncoder:
    """Test DecimalEncoder class - REFACTORED VERSION."""
    
    def test_decimal_encoder(self, common_functions):
        """Test DecimalEncoder converts Decimal to float."""
        encoder = common_functions.DecimalEncoder()
        result = encoder.default(Decimal("10.5"))
        assert result == 10.5

    def test_decimal_encoder_non_decimal(self, common_functions):
        """Test DecimalEncoder with non-Decimal value."""
        encoder = common_functions.DecimalEncoder()
        
        # Should raise TypeError for non-Decimal values
        with pytest.raises(TypeError):
            encoder.default("not a decimal")


class TestResponseGeneration:
    """Test response generation functions - REFACTORED VERSION."""
    
    def test_generate_html_response(self, common_functions):
        """Test generate_html_response creates proper response."""
        response = common_functions.generate_html_response(200, {"message": "success"})

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == {"message": "success"}
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_generate_exception_response(self, common_functions):
        """Test generate_exception_response function."""
        exception = ValueError("Test error")
        result = common_functions.generate_exception_response(exception)

        assert result["statusCode"] == 400  # Default status code for exceptions
        assert "error" in result["body"].lower()


class TestUserExtraction:
    """Test user information extraction functions - REFACTORED VERSION."""
    
    def test_get_username(self, common_functions):
        """Test get_username extracts username from event."""
        event = {"requestContext": {"authorizer": {"username": "test-user"}}}
        username = common_functions.get_username(event)
        assert username == "test-user"

    def test_get_username_default(self, common_functions):
        """Test get_username returns system when username missing."""
        event = {}
        username = common_functions.get_username(event)
        assert username == "system"

    def test_get_groups(self, common_functions):
        """Test get_groups function."""
        event = {"requestContext": {"authorizer": {"groups": '["admin", "user"]'}}}  # JSON string
        result = common_functions.get_groups(event)
        assert result == ["admin", "user"]

    def test_get_groups_missing(self, common_functions):
        """Test get_groups with missing groups."""
        event = {}
        result = common_functions.get_groups(event)
        assert result == []

    def test_get_principal_id(self, common_functions):
        """Test get_principal_id function."""
        event = {
            "requestContext": {
                "authorizer": {"principal": "test-principal-123"}  # Note: it's "principal", not "principalId"
            }
        }
        result = common_functions.get_principal_id(event)
        assert result == "test-principal-123"

    def test_get_principal_id_missing(self, common_functions):
        """Test get_principal_id with missing principalId."""
        event = {}
        result = common_functions.get_principal_id(event)
        assert result == ""


class TestTokenHandling:
    """Test token handling functions - REFACTORED VERSION."""
    
    def test_get_id_token(self, common_functions):
        """Test get_id_token function."""
        event = {"headers": {"authorization": "Bearer test-token"}}
        result = common_functions.get_id_token(event)
        assert result == "test-token"

    def test_get_id_token_missing(self, common_functions):
        """Test get_id_token with missing authorization header."""
        event = {"headers": {}}
        
        with pytest.raises(ValueError, match="Missing authorization token"):
            common_functions.get_id_token(event)

    def test_get_bearer_token(self, common_functions):
        """Test get_bearer_token function."""
        event = {"headers": {"authorization": "Bearer test-token"}}
        result = common_functions.get_bearer_token(event)
        assert result == "test-token"

    def test_get_bearer_token_with_prefix(self, common_functions):
        """Test get_bearer_token with prefix."""
        event = {"headers": {"authorization": "Bearer test-token"}}
        result = common_functions.get_bearer_token(event, with_prefix=True)
        assert result == "test-token"  # The function strips the Bearer prefix

    def test_get_bearer_token_without_prefix(self, common_functions):
        """Test get_bearer_token without prefix."""
        event = {"headers": {"authorization": "Bearer test-token"}}
        result = common_functions.get_bearer_token(event, with_prefix=False)
        assert result == "test-token"

    def test_get_bearer_token_missing(self, common_functions):
        """Test get_bearer_token with missing authorization header."""
        event = {"headers": {}}
        result = common_functions.get_bearer_token(event)
        assert result is None


class TestSessionHandling:
    """Test session handling functions - REFACTORED VERSION."""
    
    def test_get_session_id(self, common_functions):
        """Test get_session_id function."""
        event = {"pathParameters": {"sessionId": "test-session-123"}}
        result = common_functions.get_session_id(event)
        assert result == "test-session-123"

    def test_get_session_id_missing(self, common_functions):
        """Test get_session_id with missing sessionId."""
        event = {}
        result = common_functions.get_session_id(event)
        assert result is None


class TestUserAccess:
    """Test user access control functions - REFACTORED VERSION."""
    
    def test_user_has_group_access_public(self, common_functions):
        """Test user_has_group_access returns True for public resources."""
        result = common_functions.user_has_group_access(["user"], [])
        assert result is True

    def test_user_has_group_access_matching(self, common_functions):
        """Test user_has_group_access returns True when user has matching group."""
        result = common_functions.user_has_group_access(["admin", "user"], ["admin"])
        assert result is True

    def test_user_has_group_access_no_match(self, common_functions):
        """Test user_has_group_access returns False when no groups match."""
        result = common_functions.user_has_group_access(["user"], ["admin"])
        assert result is False


class TestUtilityFunctions:
    """Test utility functions - REFACTORED VERSION."""
    
    def test_merge_fields_top_level(self, common_functions):
        """Test merge_fields with top-level fields."""
        source = {"name": "John", "age": 30, "city": "NYC"}
        target = {"country": "USA"}
        fields = ["name", "age"]

        result = common_functions.merge_fields(source, target, fields)

        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["country"] == "USA"
        assert "city" not in result

    def test_get_item(self, common_functions):
        """Test get_item function."""
        response = {"Items": [{"test": "value"}]}
        result = common_functions.get_item(response)
        assert result == {"test": "value"}

    def test_get_item_missing(self, common_functions):
        """Test get_item with missing Items."""
        response = {}
        result = common_functions.get_item(response)
        assert result is None


class TestLoggingSetup:
    """Test logging setup functions - REFACTORED VERSION."""
    
    def test_setup_root_logging(self, mock_common_functions, common_functions):
        """Test setup_root_logging function."""
        # Reset logging configuration flag if it exists
        if hasattr(common_functions, 'logging_configured'):
            common_functions.logging_configured = False
        
        common_functions.setup_root_logging()

        # Check that logging was configured (global variable should be True)
        assert common_functions.logging_configured is True

    def test_sanitize_event(self, common_functions):
        """Test _sanitize_event function."""
        event = {
            "headers": {"Authorization": "Bearer token", "Content-Type": "application/json"}, 
            "body": "test body"
        }

        result = common_functions._sanitize_event(event)
        assert isinstance(result, str)
        # Should contain sanitized headers
        assert "authorization" in result.lower()


class TestDecorators:
    """Test decorator functions - REFACTORED VERSION."""
    
    def test_api_wrapper_success(self, common_functions, lambda_context):
        """Test api_wrapper with successful function execution."""
        @common_functions.api_wrapper
        def test_function(event, context):
            return {"message": "success"}

        event = {"test": "data"}
        result = test_function(event, lambda_context)
        
        assert result["statusCode"] == 200
        assert "success" in result["body"]

    def test_api_wrapper_exception(self, common_functions, lambda_context):
        """Test api_wrapper with exception handling."""
        @common_functions.api_wrapper
        def test_function(event, context):
            raise ValueError("Test error")

        event = {"test": "data"}
        result = test_function(event, lambda_context)
        
        assert result["statusCode"] == 400  # Default status code for exceptions
        assert "error" in result["body"].lower()

    def test_authorization_wrapper_success(self, common_functions, lambda_context):
        """Test authorization_wrapper with successful authorization."""
        @common_functions.authorization_wrapper
        def test_function(event, context):
            return {"message": "success"}

        event = {"requestContext": {"authorizer": {"username": "test-user", "groups": ["admin"]}}}
        result = test_function(event, lambda_context)
        
        # The authorization_wrapper just calls the function directly
        assert result == {"message": "success"}

    def test_authorization_wrapper_no_authorizer(self, common_functions, lambda_context):
        """Test authorization_wrapper with missing authorizer."""
        @common_functions.authorization_wrapper
        def test_function(event, context):
            return {"message": "success"}

        event = {}
        result = test_function(event, lambda_context)
        
        # The authorization_wrapper just calls the function directly
        assert result == {"message": "success"}


class TestValidationModule:
    """Test validation module functions - REFACTORED VERSION."""
    
    def test_validate_model_name_valid(self, validation_module):
        """Test validate_model_name with valid model name."""
        result = validation_module.validate_model_name("valid-model-123")
        assert result is True

    def test_validate_model_name_empty(self, validation_module):
        """Test validate_model_name raises ValidationError for empty string."""
        with pytest.raises(validation_module.ValidationError):
            validation_module.validate_model_name("")


class TestValidatorsModule:
    """Test validators module functions - REFACTORED VERSION."""
    
    def test_validate_instance_type_valid(self, validators_module):
        """Test validate_instance_type with valid EC2 instance type."""
        result = validators_module.validate_instance_type("t3.micro")
        assert result == "t3.micro"

    def test_validate_all_fields_defined_true(self, validators_module):
        """Test validate_all_fields_defined returns True when all fields are non-null."""
        result = validators_module.validate_all_fields_defined(["value1", "value2", "value3"])
        assert result is True

    def test_validate_all_fields_defined_false(self, validators_module):
        """Test validate_all_fields_defined returns False when any field is None."""
        result = validators_module.validate_all_fields_defined(["value1", None, "value3"])
        assert result is False
