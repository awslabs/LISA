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

# Set up environment
os.environ["AWS_REGION"] = "us-east-1"

# Add REST API to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib/serve/rest-api/src/utils"))

from rds_auth import _get_lambda_role_arn, get_lambda_role_name


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
