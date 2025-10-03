"""
Refactored tests for model_api_key_cleanup Lambda function using fixture-based mocking.
Replaces global mocks with proper fixtures for better test isolation.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))


@pytest.fixture
def mock_model_api_key_cleanup_common():
    """Common mocks for model_api_key_cleanup tests."""
    with patch.dict("os.environ", {
        "AWS_REGION": "us-east-1",
        "DEPLOYMENT_PREFIX": "/test/LISA/lisa"
    }):
        yield


@pytest.fixture
def model_api_key_cleanup_functions():
    """Import model_api_key_cleanup functions."""
    from models.model_api_key_cleanup import get_database_connection, lambda_handler
    return {
        'get_database_connection': get_database_connection,
        'lambda_handler': lambda_handler
    }


@pytest.fixture
def mock_database_connection():
    """Mock database connection and cursor."""
    mock_connection = Mock()
    mock_cursor = Mock()
    mock_connection.cursor.return_value = mock_cursor
    return {
        'connection': mock_connection,
        'cursor': mock_cursor
    }


@pytest.fixture
def mock_boto3_clients():
    """Mock boto3 SSM and Secrets Manager clients."""
    mock_ssm_client = Mock()
    mock_secrets_client = Mock()
    
    with patch("models.model_api_key_cleanup.boto3.client") as mock_boto3_client:
        mock_boto3_client.side_effect = [mock_ssm_client, mock_secrets_client]
        yield {
            'ssm_client': mock_ssm_client,
            'secrets_client': mock_secrets_client,
            'boto3_client': mock_boto3_client
        }


@pytest.fixture
def sample_cloudformation_event():
    """Sample CloudFormation event."""
    return {
        "RequestType": "Create",
        "ResponseURL": "https://cloudformation-custom-resource-response-useast1.s3.amazonaws.com/test",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
        "RequestId": "unique-request-id",
        "LogicalResourceId": "BedrockAuthCleanup"
    }


@pytest.fixture
def sample_delete_event():
    """Sample delete CloudFormation event."""
    return {
        "RequestType": "Delete",
        "ResponseURL": "https://cloudformation-custom-resource-response-useast1.s3.amazonaws.com/test",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
        "RequestId": "unique-request-id",
        "LogicalResourceId": "BedrockAuthCleanup"
    }


@pytest.fixture
def sample_context():
    """Sample Lambda context."""
    context = Mock()
    context.aws_request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/test-function"
    context.log_stream_name = "2023/01/01/[$LATEST]1234567890"
    context.function_name = "test-function"
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = 30000
    return context


class TestLambdaHandler:
    """Test cases for lambda_handler function with fixture-based mocking."""

    def test_lambda_handler_delete_request_type(
        self, 
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_delete_event,
        sample_context
    ):
        """Test that DELETE request type still processes but returns SUCCESS."""
        mock_database_connection['cursor'].fetchall.return_value = []
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_delete_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"

    def test_lambda_handler_success(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test successful execution."""
        mock_database_connection['cursor'].fetchall.return_value = [("model-1", '{"api_key": "ignored"}')]
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert "ModelsUpdated" in result["Data"]

    def test_lambda_handler_exception(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        sample_cloudformation_event,
        sample_context
    ):
        """Test exception handling."""
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.side_effect = Exception("Database connection failed")
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "FAILED"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert "Database connection failed" in result["Reason"]

    def test_lambda_handler_no_tables_found(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test when no LiteLLM tables are found in database."""
        mock_database_connection['cursor'].fetchall.return_value = []  # No tables found
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert result["Data"]["ModelsUpdated"] == "0"

    def test_lambda_handler_table_found_but_no_models(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test when LiteLLM table is found but no models need updating."""
        # Mock table discovery
        mock_database_connection['cursor'].fetchall.side_effect = [
            [("LiteLLM_ProxyModelTable",)],  # Tables found
            [("id", "model_name", "litellm_params")],  # Column info
            [],  # No models with api_key
        ]
        mock_database_connection['cursor'].description = [("id",), ("model_name",), ("litellm_params",)]
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert "ModelsUpdated" in result["Data"]

    def test_lambda_handler_missing_columns(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test when required columns are not found in the table."""
        # Mock table discovery but missing required columns
        mock_database_connection['cursor'].fetchall.return_value = [("LiteLLM_ProxyModelTable",)]
        mock_database_connection['cursor'].description = [("some_column",), ("other_column",)]  # Missing required columns
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert result["Data"]["ModelsUpdated"] == "0"


class TestDatabaseConnection:
    """Test cases for get_database_connection function with fixture-based mocking."""

    def test_get_database_connection_success(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_boto3_clients
    ):
        """Test successful database connection."""
        # Mock SSM parameter response
        mock_boto3_clients['ssm_client'].get_parameter.return_value = {
            "Parameter": {
                "Value": json.dumps({
                    "dbHost": "test-host",
                    "dbPort": "5432",
                    "dbName": "testdb",
                    "username": "testuser",
                    "passwordSecretId": "test-secret",
                })
            }
        }

        # Mock Secrets Manager response
        mock_boto3_clients['secrets_client'].get_secret_value.return_value = {
            "SecretString": json.dumps({"username": "testuser", "password": "testpass"})
        }

        with patch("models.model_api_key_cleanup.psycopg2.connect") as mock_connect:
            mock_connection = Mock()
            mock_connect.return_value = mock_connection
            
            result = model_api_key_cleanup_functions['get_database_connection']()
            
            assert result == mock_connection
            mock_connect.assert_called_once()

    def test_get_database_connection_ssm_error(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_boto3_clients
    ):
        """Test SSM parameter retrieval failure."""
        mock_boto3_clients['ssm_client'].get_parameter.side_effect = Exception("SSM error")
        
        with pytest.raises(Exception, match="SSM error"):
            model_api_key_cleanup_functions['get_database_connection']()

    def test_get_database_connection_secrets_error(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions
    ):
        """Test Secrets Manager error during database connection."""
        mock_ssm_client = Mock()
        mock_secrets_client = Mock()

        with patch("models.model_api_key_cleanup.boto3.client") as mock_boto3_client:
            mock_boto3_client.side_effect = [mock_ssm_client, mock_secrets_client]

            # Mock SSM parameter response
            mock_ssm_client.get_parameter.return_value = {
                "Parameter": {
                    "Value": json.dumps({
                        "dbHost": "test-host",
                        "dbPort": "5432",
                        "dbName": "testdb",
                        "username": "testuser",
                        "passwordSecretId": "test-secret",
                    })
                }
            }

            # Mock Secrets Manager error
            mock_secrets_client.get_secret_value.side_effect = Exception("Secrets error")

            with pytest.raises(Exception, match="Secrets error"):
                model_api_key_cleanup_functions['get_database_connection']()


class TestPostgreSQLCleanup:
    """Test cases for PostgreSQL database cleanup operations with fixture-based mocking."""

    def test_complex_database_operations(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test complex database operations with multiple models."""
        # Mock complex database response with multiple models
        mock_database_connection['cursor'].fetchall.side_effect = [
            [("LiteLLM_ProxyModelTable",)],  # Tables found
            [("id", "model_name", "litellm_params")],  # Column info
            [
                ("model-1", '{"api_key": "sk-1234", "model": "gpt-4"}'),
                ("model-2", '{"api_key": "sk-5678", "model": "claude-3"}'),
                ("model-3", '{"model": "bedrock/anthropic.claude-v2"}')  # No api_key
            ]  # Models with and without api_keys
        ]
        mock_database_connection['cursor'].description = [("id",), ("model_name",), ("litellm_params",)]
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert "ModelsUpdated" in result["Data"]

    def test_database_transaction_handling(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test database transaction handling during cleanup."""
        # Mock database operations with transaction
        mock_database_connection['cursor'].fetchall.side_effect = [
            [("LiteLLM_ProxyModelTable",)],  # Tables found
            [("id", "model_name", "litellm_params")],  # Column info
            [("model-1", '{"api_key": "sk-1234"}')]  # Model with api_key
        ]
        mock_database_connection['cursor'].description = [("id",), ("model_name",), ("litellm_params",)]
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            # Verify transaction methods were called
            mock_database_connection['connection'].commit.assert_called()

    def test_database_connection_cleanup(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test that database connections are properly cleaned up."""
        mock_database_connection['cursor'].fetchall.return_value = []
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            # Verify connection cleanup
            mock_database_connection['connection'].close.assert_called()


class TestCloudFormationIntegration:
    """Test cases for CloudFormation custom resource integration with fixture-based mocking."""

    def test_cloudformation_response_format(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_cloudformation_event,
        sample_context
    ):
        """Test CloudFormation response format compliance."""
        mock_database_connection['cursor'].fetchall.return_value = []
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            # Verify CloudFormation response format
            assert "Status" in result
            assert "PhysicalResourceId" in result
            assert "Data" in result
            assert result["Status"] in ["SUCCESS", "FAILED"]
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"

    def test_update_request_type(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        mock_database_connection,
        sample_context
    ):
        """Test handling of UPDATE request type."""
        update_event = {
            "RequestType": "Update",
            "ResponseURL": "https://cloudformation-custom-resource-response-useast1.s3.amazonaws.com/test",
            "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
            "RequestId": "unique-request-id",
            "LogicalResourceId": "BedrockAuthCleanup"
        }
        
        mock_database_connection['cursor'].fetchall.return_value = []
        
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_database_connection['connection']
            
            result = model_api_key_cleanup_functions['lambda_handler'](update_event, sample_context)
            
            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"

    def test_error_response_format(
        self,
        mock_model_api_key_cleanup_common,
        model_api_key_cleanup_functions,
        sample_cloudformation_event,
        sample_context
    ):
        """Test error response format for CloudFormation."""
        with patch("models.model_api_key_cleanup.get_database_connection") as mock_get_connection:
            mock_get_connection.side_effect = Exception("Critical database error")
            
            result = model_api_key_cleanup_functions['lambda_handler'](sample_cloudformation_event, sample_context)
            
            assert result["Status"] == "FAILED"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert "Reason" in result
            assert "Critical database error" in result["Reason"]
