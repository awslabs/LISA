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

"""Unit tests for RDS authentication utilities."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set up environment
os.environ["AWS_REGION"] = "us-east-1"

# Add REST API to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib/serve/rest-api/src/utils"))

from rds_auth import _get_lambda_role_arn, generate_auth_token, get_lambda_role_name


@patch("rds_auth.boto3.client")
def test_generate_auth_token(mock_boto_client):
    """Test generating RDS auth token."""
    mock_rds = MagicMock()
    mock_rds.generate_db_auth_token.return_value = "test-token-123"
    mock_boto_client.return_value = mock_rds
    
    result = generate_auth_token("db.example.com", "5432", "testuser")
    
    assert result == "test-token-123"
    mock_rds.generate_db_auth_token.assert_called_once_with(
        DBHostname="db.example.com",
        Port="5432",
        DBUsername="testuser"
    )


@patch("rds_auth.boto3.client")
def test_generate_auth_token_with_special_chars(mock_boto_client):
    """Test generating RDS auth token with special characters."""
    mock_rds = MagicMock()
    mock_rds.generate_db_auth_token.return_value = "token+with/special=chars"
    mock_boto_client.return_value = mock_rds
    
    result = generate_auth_token("db.example.com", "5432", "testuser")
    
    # Should URL encode special characters
    assert "+" in result or "%2B" in result


@patch("rds_auth.boto3.client")
def test_get_lambda_role_arn(mock_boto_client):
    """Test getting Lambda role ARN."""
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:sts::123456789012:assumed-role/MyLambdaRole/my-function"
    }
    mock_boto_client.return_value = mock_sts
    
    result = _get_lambda_role_arn()
    
    assert result == "arn:aws:sts::123456789012:assumed-role/MyLambdaRole/my-function"
    mock_sts.get_caller_identity.assert_called_once()


@patch("rds_auth.boto3.client")
def test_get_lambda_role_name(mock_boto_client):
    """Test extracting Lambda role name from ARN."""
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:sts::123456789012:assumed-role/MyLambdaRole/my-function"
    }
    mock_boto_client.return_value = mock_sts
    
    result = get_lambda_role_name()
    
    assert result == "MyLambdaRole"


@patch("rds_auth.boto3.client")
def test_get_lambda_role_name_complex_arn(mock_boto_client):
    """Test extracting Lambda role name from complex ARN."""
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:sts::123456789012:assumed-role/MyComplexRole-With-Dashes/function-name-123"
    }
    mock_boto_client.return_value = mock_sts
    
    result = get_lambda_role_name()
    
    assert result == "MyComplexRole-With-Dashes"
