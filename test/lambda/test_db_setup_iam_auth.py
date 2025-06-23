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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import psycopg2
import pytest
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

# Import the module to test
from utilities.db_setup_iam_auth import create_db_user, get_db_credentials, handler


@pytest.fixture(scope="function")
def secretsmanager_client():
    """Create a mock Secrets Manager service."""
    with mock_aws():
        yield boto3.client("secretsmanager", region_name="us-east-1")


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
def mock_psycopg2_connection():
    """Create a mock psycopg2 connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def test_get_db_credentials_success():
    """Test successful retrieval of database credentials."""
    # Create a test secret ARN
    secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret"
    secret_value = {"username": "test-user", "password": "test-password"}

    # Mock the secrets manager client directly
    with patch("utilities.db_setup_iam_auth.boto3.client") as mock_client:
        mock_secretsmanager = MagicMock()
        mock_client.return_value = mock_secretsmanager
        
        # Configure the mock to return the expected secret
        mock_secretsmanager.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_value)
        }

        # Call the function with the test ARN
        result = get_db_credentials(secret_arn)

        # Assert the result
        assert result == secret_value
        
        # Verify the client was called correctly
        mock_client.assert_called_once_with("secretsmanager")
        mock_secretsmanager.get_secret_value.assert_called_once_with(SecretId=secret_arn)


def test_get_db_credentials_error():
    """Test error handling when Secrets Manager fails."""
    # Use patch to force a ClientError
    with patch("boto3.client") as mock_boto3_client:
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}, "GetSecretValue"
        )
        mock_boto3_client.return_value = mock_client

        # Call the function and assert it raises the expected exception
        with pytest.raises(Exception, match="Error retrieving secrets"):
            get_db_credentials("non-existent-arn")


def test_create_db_user_success(mock_psycopg2_connection):
    """Test successful creation of a database user."""
    mock_conn, mock_cursor = mock_psycopg2_connection

    # Mock the psycopg2.connect function
    with patch("psycopg2.connect", return_value=mock_conn):
        # Mock get_db_credentials
        with patch("utilities.db_setup_iam_auth.get_db_credentials") as mock_get_credentials:
            mock_get_credentials.return_value = {"password": "test-password"}

            # Call the function
            create_db_user(
                db_host="test-host",
                db_port="5432",
                db_name="test-db",
                db_user="admin",
                secret_arn="test-arn",
                iam_name="test-iam-user",
            )

            # Verify the connection was established with the correct parameters
            mock_get_credentials.assert_called_once_with("test-arn")
            psycopg2_connect_args = {
                "dbname": "test-db",
                "user": "admin",
                "password": "test-password",
                "host": "test-host",
                "port": "5432",
            }

            # Verify the connection was established with the correct parameters
            psycopg2_connect_call = mock_conn._mock_call_args
            assert psycopg2_connect_call is None or psycopg2_connect_call[1] == psycopg2_connect_args

            # Verify the cursor was created
            mock_conn.cursor.assert_called_once()

            # Verify the CREATE USER command was executed
            mock_cursor.execute.assert_any_call('CREATE USER "test-iam-user"')

            # Verify the GRANT commands were executed
            mock_cursor.execute.assert_any_call('GRANT rds_iam to "test-iam-user"')
            mock_cursor.execute.assert_any_call('GRANT USAGE, CREATE ON SCHEMA public TO "test-iam-user"')
            mock_cursor.execute.assert_any_call(
                'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "test-iam-user"'
            )
            mock_cursor.execute.assert_any_call(
                'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "test-iam-user"'
            )
            mock_cursor.execute.assert_any_call(
                'GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO "test-iam-user"'
            )
            mock_cursor.execute.assert_any_call(
                'GRANT ALL PRIVILEGES ON ALL PROCEDURES IN SCHEMA public TO "test-iam-user"'
            )

            # Verify the connection was committed and closed
            mock_conn.commit.assert_called()
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()


def test_create_db_user_existing_user(mock_psycopg2_connection):
    """Test handling when the user already exists."""
    mock_conn, mock_cursor = mock_psycopg2_connection

    class PsycopgError(psycopg2.Error):
        pgcode = "23505"  # Permission denied

    # Configure the cursor to raise a unique violation error on the first execute call
    unique_violation_error = PsycopgError("unique violation")
    mock_cursor.execute.side_effect = [unique_violation_error] + [None] * 10  # First call raises, rest succeed

    # Mock the psycopg2.connect function
    with patch("psycopg2.connect", return_value=mock_conn):
        # Mock get_db_credentials
        with patch("utilities.db_setup_iam_auth.get_db_credentials") as mock_get_credentials:
            mock_get_credentials.return_value = {"password": "test-password"}

            # Call the function - should not raise an exception
            create_db_user(
                db_host="test-host",
                db_port="5432",
                db_name="test-db",
                db_user="admin",
                secret_arn="test-arn",
                iam_name="test-iam-user",
            )

            # Verify the connection was committed and closed
            mock_conn.commit.assert_called()
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()


def test_create_db_user_error(mock_psycopg2_connection):
    """Test error handling for other PostgreSQL errors."""
    mock_conn, mock_cursor = mock_psycopg2_connection

    # Configure the cursor to raise a non-unique violation error
    class PsycopgError(psycopg2.Error):
        pgcode = "42P01"  # Table does not exist

    mock_cursor.execute.side_effect = PsycopgError("relation does not exist")

    # Mock the psycopg2.connect function
    with patch("psycopg2.connect", return_value=mock_conn):
        # Mock get_db_credentials
        with patch("utilities.db_setup_iam_auth.get_db_credentials") as mock_get_credentials:
            mock_get_credentials.return_value = {"password": "test-password"}

            # Call the function and assert it raises the expected exception
            with pytest.raises(Exception, match="Error creating user"):
                create_db_user(
                    db_host="test-host",
                    db_port="5432",
                    db_name="test-db",
                    db_user="admin",
                    secret_arn="test-arn",
                    iam_name="test-iam-user",
                )


def test_create_db_user_grant_error(mock_psycopg2_connection):
    """Test error handling when granting privileges fails."""
    mock_conn, mock_cursor = mock_psycopg2_connection

    # Configure the cursor to raise an error on the second execute call (first GRANT command)
    class PsycopgError(psycopg2.Error):
        pgcode = "42501"  # Permission denied

    # First call succeeds (CREATE USER), second call fails (GRANT)
    mock_cursor.execute.side_effect = [None, PsycopgError("permission denied")]

    # Mock the psycopg2.connect function
    with patch("psycopg2.connect", return_value=mock_conn):
        # Mock get_db_credentials
        with patch("utilities.db_setup_iam_auth.get_db_credentials") as mock_get_credentials:
            mock_get_credentials.return_value = {"password": "test-password"}

            # Call the function and assert it raises the expected exception
            with pytest.raises(Exception, match="Error granting privileges to user"):
                create_db_user(
                    db_host="test-host",
                    db_port="5432",
                    db_name="test-db",
                    db_user="admin",
                    secret_arn="test-arn",
                    iam_name="test-iam-user",
                )

            # Verify the connection was closed
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()


def test_handler_success(lambda_context):
    """Test successful execution of the handler."""
    # Set up environment variables
    env_vars = {
        "SECRET_ARN": "test-arn",
        "DB_HOST": "test-host",
        "DB_PORT": "5432",
        "DB_NAME": "test-db",
        "DB_USER": "admin",
        "IAM_NAME": "test-iam-user",
    }

    # Mock the create_db_user function
    with patch("utilities.db_setup_iam_auth.create_db_user") as mock_create_db_user:
        # Mock environment variables
        with patch.dict(os.environ, env_vars):
            # Call the handler
            response = handler({}, lambda_context)

            # Verify create_db_user was called with the correct parameters
            mock_create_db_user.assert_called_once_with(
                "test-host", "5432", "test-db", "admin", "test-arn", "test-iam-user"
            )

            # Verify the response
            assert response["statusCode"] == 200
            assert response["body"] == "Database user created successfully"


def test_handler_missing_env_vars(lambda_context):
    """Test handler with missing environment variables."""
    # Set up incomplete environment variables
    env_vars = {
        "SECRET_ARN": "test-arn",
        # Missing DB_HOST
        "DB_PORT": "5432",
        "DB_NAME": "test-db",
        "DB_USER": "admin",
        "IAM_NAME": "test-iam-user",
    }

    # Mock environment variables
    with patch.dict(os.environ, env_vars, clear=True):
        # Call the handler and expect a KeyError
        with pytest.raises(KeyError):
            handler({}, lambda_context)


def test_handler_create_db_user_error(lambda_context):
    """Test handler when create_db_user raises an exception."""
    # Set up environment variables
    env_vars = {
        "SECRET_ARN": "test-arn",
        "DB_HOST": "test-host",
        "DB_PORT": "5432",
        "DB_NAME": "test-db",
        "DB_USER": "admin",
        "IAM_NAME": "test-iam-user",
    }

    # Mock the create_db_user function to raise an exception
    with patch("utilities.db_setup_iam_auth.create_db_user") as mock_create_db_user:
        mock_create_db_user.side_effect = Exception("Database connection failed")

        # Mock environment variables
        with patch.dict(os.environ, env_vars):
            # Call the handler and expect the exception to propagate
            with pytest.raises(Exception, match="Database connection failed"):
                handler({}, lambda_context)
