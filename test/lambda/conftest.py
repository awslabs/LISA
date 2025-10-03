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

import pytest
from unittest.mock import Mock, patch, MagicMock
from types import SimpleNamespace
import json
import os
import boto3
from moto import mock_aws


@pytest.fixture(autouse=True)
def aws_env_vars():
    """Common AWS environment variables fixture for testing - auto-applied to all tests."""
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "MODEL_TABLE_NAME": "test-model-table",
        "LISA_INGESTION_JOB_TABLE_NAME": "test-ingestion-job-table",
        "LISA_RAG_VECTOR_STORE_TABLE": "test-vector-store-table",
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def sample_jwt_data():
    """Create a sample JWT data."""
    return {"sub": "test-user-id", "username": "test-user", "groups": ["test-group"], "nested": {"property": "value"}}


@pytest.fixture
def lambda_context():
    """Create a mock lambda context."""
    context = SimpleNamespace()
    context.function_name = "test-function"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/test-function"
    context.log_stream_name = "test-stream"
    return context


@pytest.fixture
def mock_auth_context():
    """Mock authentication context for regular user."""
    with patch('utilities.auth.get_groups') as mock_get_groups, \
         patch('utilities.auth.is_admin') as mock_is_admin, \
         patch('utilities.auth.get_username') as mock_get_username, \
         patch('utilities.auth.get_user_context') as mock_get_user_context:
        
        mock_get_groups.return_value = ["user-group"]
        mock_is_admin.return_value = False
        mock_get_username.return_value = "test-user"
        mock_get_user_context.return_value = ("test-user", False)
        
        yield {
            'get_groups': mock_get_groups,
            'is_admin': mock_is_admin,
            'get_username': mock_get_username,
            'get_user_context': mock_get_user_context
        }


@pytest.fixture
def mock_admin_auth_context():
    """Mock authentication context for admin user."""
    with patch('utilities.auth.get_groups') as mock_get_groups, \
         patch('utilities.auth.is_admin') as mock_is_admin, \
         patch('utilities.auth.get_username') as mock_get_username, \
         patch('utilities.auth.get_user_context') as mock_get_user_context:
        
        mock_get_groups.return_value = ["admin-group"]
        mock_is_admin.return_value = True
        mock_get_username.return_value = "admin-user"
        mock_get_user_context.return_value = ("admin-user", True)
        
        yield {
            'get_groups': mock_get_groups,
            'is_admin': mock_is_admin,
            'get_username': mock_get_username,
            'get_user_context': mock_get_user_context
        }


@pytest.fixture 
def mock_repositories():
    """Mock repository dependencies."""
    with patch('repository.lambda_functions.vs_repo') as mock_vs_repo, \
         patch('repository.lambda_functions.ingestion_job_repository') as mock_job_repo:
        
        # Configure vector store repository mock
        mock_vs_repo.find_repository_by_id.return_value = {
            "repositoryId": "test-repo",  
            "allowedGroups": ["admin-group"],
            "type": "opensearch"
        }
        
        # Configure ingestion job repository mock
        mock_job_repo.list_jobs_by_repository.return_value = ([], None)
        
        yield {
            'vs_repo': mock_vs_repo,
            'job_repo': mock_job_repo
        }


@pytest.fixture
def mock_repository_services():
    """Mock repository service dependencies with proper data types for pydantic validation."""
    # Mock vector store repository
    mock_vs_repo = MagicMock()
    mock_vs_repo.find_repository_by_id.return_value = {
        "repositoryId": "test-repo",
        "name": "Test Repository",
        "collectionId": "test-collection",  # String value, not MagicMock
        "allowedGroups": ["test-group"],
        "type": "opensearch",
        "status": "active"
    }
    
    # Configure get_registered_repositories to return a list of repositories
    mock_vs_repo.get_registered_repositories.return_value = [
        {
            "repositoryId": "test-repo",
            "name": "Test Repository",
            "allowedGroups": ["test-group"],
            "type": "opensearch",
            "status": "active"
        }
    ]
    
    # Configure get_repository_status to return repository statuses
    mock_vs_repo.get_repository_status.return_value = {
        "test-repo": "active"
    }
    
    # Mock document repository
    mock_doc_repo = MagicMock()
    mock_doc_repo.find_by_id.return_value = {
        "document_id": "test-doc",
        "username": "test-user",
        "repository_id": "test-repo",
        "source": "s3://test-bucket/test-key"
    }
    
    # Mock ingestion service
    mock_ingestion_service = MagicMock()
    mock_ingestion_service.create_delete_job.return_value = None
    
    yield {
        'vs_repo': mock_vs_repo,
        'doc_repo': mock_doc_repo,
        'ingestion_service': mock_ingestion_service
    }


@pytest.fixture
def mock_aws_magicmock_services():
    """Pure MagicMock AWS services for tests that need to set return_value attributes."""
    mock_ssm = MagicMock()
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-arn"}}
    mock_ssm.put_parameter.return_value = {}
    
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://test-presigned-url"
    mock_s3.generate_presigned_post.return_value = {
        "url": "https://test-bucket.s3.amazonaws.com",
        "fields": {"key": "test-key"}
    }
    
    mock_stepfunctions = MagicMock()
    mock_stepfunctions.start_execution.return_value = {"executionArn": "test-execution-arn"}
    
    mock_bedrock = MagicMock()
    mock_bedrock.retrieve.return_value = {"retrievalResults": []}
    
    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}
    
    mock_dynamodb = MagicMock()
    
    yield {
        'ssm': mock_ssm,
        's3': mock_s3,
        'stepfunctions': mock_stepfunctions,
        'bedrock': mock_bedrock,
        'bedrock-agent-runtime': mock_bedrock,
        'cloudwatch': mock_cloudwatch,
        'dynamodb': mock_dynamodb
    }


@pytest.fixture
def aws_moto_services():
    """Real moto-based AWS service mocks."""
    with mock_aws():
        # Create real AWS services using moto
        ssm = boto3.client("ssm", region_name="us-east-1")
        s3 = boto3.client("s3", region_name="us-east-1")
        stepfunctions = boto3.client("stepfunctions", region_name="us-east-1")
        secretsmanager = boto3.client("secretsmanager", region_name="us-east-1")
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        
        # Create some default parameters in SSM
        ssm.put_parameter(
            Name="test-api-url",
            Value="https://api.test.com",
            Type="String"
        )
        ssm.put_parameter(
            Name="test-secret-name",
            Value="test-secret-arn",
            Type="String"
        )
        ssm.put_parameter(
            Name="test-repositories",
            Value=json.dumps([{"repositoryId": "test-repo", "name": "Test Repository"}]),
            Type="String"
        )
        ssm.put_parameter(
            Name="test-state-machine-arn",
            Value="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            Type="String"
        )
        ssm.put_parameter(
            Name="test-create-state-machine-arn",
            Value="arn:aws:states:us-east-1:123456789012:stateMachine:test-create",
            Type="String"
        )
        
        # Create S3 bucket
        s3.create_bucket(Bucket="test-bucket")
        
        # Create secret in Secrets Manager
        secretsmanager.create_secret(
            Name="test-secret",
            SecretString=json.dumps({"password": "test-password"})
        )
        
        yield {
            'ssm': ssm,
            's3': s3,
            'stepfunctions': stepfunctions,
            'secretsmanager': secretsmanager,
            'dynamodb': dynamodb
        }


@pytest.fixture
def mock_aws_services():
    """Mock common AWS service clients - combines moto services with MagicMock for unsupported services."""
    with mock_aws():
        # Create real AWS services using moto
        ssm = boto3.client("ssm", region_name="us-east-1")
        s3 = boto3.client("s3", region_name="us-east-1")
        stepfunctions = boto3.client("stepfunctions", region_name="us-east-1")
        secretsmanager = boto3.client("secretsmanager", region_name="us-east-1")
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        
        # Create some default parameters in SSM
        ssm.put_parameter(
            Name="test-api-url",
            Value="https://api.test.com",
            Type="String"
        )
        ssm.put_parameter(
            Name="test-secret-name",
            Value="test-secret-arn",
            Type="String"
        )
        ssm.put_parameter(
            Name="test-repositories",
            Value=json.dumps([{"repositoryId": "test-repo", "name": "Test Repository"}]),
            Type="String"
        )
        ssm.put_parameter(
            Name="test-state-machine-arn",
            Value="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            Type="String"
        )
        ssm.put_parameter(
            Name="test-create-state-machine-arn",
            Value="arn:aws:states:us-east-1:123456789012:stateMachine:test-create",
            Type="String"
        )
        
        # Create S3 bucket
        s3.create_bucket(Bucket="test-bucket")
        
        # Create secret in Secrets Manager
        secretsmanager.create_secret(
            Name="test-secret",
            SecretString=json.dumps({"password": "test-password"})
        )
        
        # Mock Bedrock client (not supported by moto)
        mock_bedrock = MagicMock()
        mock_bedrock.retrieve.return_value = {"retrievalResults": []}
        
        # Mock CloudWatch client
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.put_metric_data.return_value = {}
        
        yield {
            'ssm': ssm,
            's3': s3,
            'stepfunctions': stepfunctions,
            'secretsmanager': secretsmanager,
            'dynamodb': dynamodb,
            'bedrock': mock_bedrock,
            'bedrock-agent-runtime': mock_bedrock,
            'cloudwatch': mock_cloudwatch
        }


@pytest.fixture 
def mock_session_auth():
    """Mock authentication for session lambda tests."""
    def get_username_from_event(event):
        return event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("username", "test-user")
    
    def get_session_id_from_event(event):
        return event.get("pathParameters", {}).get("sessionId", "test-session")
    
    with patch('utilities.auth.get_username', side_effect=get_username_from_event) as mock_get_username, \
         patch('utilities.common_functions.get_session_id', side_effect=get_session_id_from_event) as mock_get_session_id:
        
        yield {
            'get_username': mock_get_username,
            'get_session_id': mock_get_session_id
        }


@pytest.fixture(autouse=True)
def mock_missing_modules():
    """Mock commonly missing modules that cause import errors."""
    # Mock create_env_variables module that's imported by various lambda functions
    mock_create_env = MagicMock()
    
    with patch.dict('sys.modules', {
        'create_env_variables': mock_create_env,
    }):
        yield


@pytest.fixture
def mock_api_wrapper_bypass():
    """Mock api_wrapper to bypass it and test functions naturally."""
    with patch('utilities.common_functions.api_wrapper', lambda func: func):
        yield


@pytest.fixture
def mock_api_wrapper_http():
    """Mock the api_wrapper to return proper HTTP responses for integration testing."""
    def wrapper(func):
        def inner(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if isinstance(result, dict) and "statusCode" in result:
                    return result
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps(result, default=str),
                }
            except ValueError as e:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": str(e)}),
                }
            except Exception as e:
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": str(e)}),
                }
        return inner
    
    with patch('utilities.common_functions.api_wrapper', side_effect=wrapper):
        yield wrapper


class RepositoryTestHelper:
    """Helper class for creating test events for repository lambda tests."""
    
    @staticmethod
    def create_admin_event(repository_id: str, queryStringParameters=None):
        """Create a test event for an admin user."""
        return {
            "requestContext": {
                "authorizer": {
                    "username": "admin-user",
                    "groups": '["admin-group"]'
                }
            },
            "pathParameters": {
                "repositoryId": repository_id
            },
            "queryStringParameters": queryStringParameters or {}
        }
    
    @staticmethod
    def create_user_event(repository_id: str, username: str = "test-user", queryStringParameters=None):
        """Create a test event for a regular user."""
        return {
            "requestContext": {
                "authorizer": {
                    "username": username,
                    "groups": '["user-group"]'
                }
            },
            "pathParameters": {
                "repositoryId": repository_id
            },
            "queryStringParameters": queryStringParameters or {}
        }
    
    @staticmethod
    def create_repository_event(username: str, groups: list, path_params=None, query_params=None, body=None):
        """Create a test event for repository operations."""
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {"username": username},
                    "groups": json.dumps(groups)
                }
            },
            "pathParameters": path_params or {},
            "queryStringParameters": query_params or {},
            "headers": {"authorization": "Bearer test-token"}
        }
        if body:
            event["body"] = json.dumps(body) if isinstance(body, dict) else body
        return event


class SessionTestHelper:
    """Helper class for creating test events for session lambda tests."""
    
    @staticmethod
    def create_session_event(session_id: str = "test-session", username: str = "test-user", **kwargs):
        """Create a test event for session operations."""
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "username": username
                    }
                }
            },
            "pathParameters": {
                "sessionId": session_id
            }
        }
        event.update(kwargs)
        return event
    
    @staticmethod
    def create_session_data(session_id: str = "test-session", user_id: str = "test-user"):
        """Create sample session data."""
        return {
            "sessionId": session_id,
            "userId": user_id,
            "history": [
                {"type": "human", "content": "Hello"},
                {"type": "assistant", "content": "Hi there!"}
            ],
            "configuration": {"model": "test-model"},
            "startTime": "2024-01-01T00:00:00",
            "createTime": "2024-01-01T00:00:00"
        }


class LambdaTestHelper:
    """Generic helper class for lambda test events."""
    
    @staticmethod
    def create_basic_event(username: str = "test-user", path_params=None, query_params=None, body=None):
        """Create a basic lambda event."""
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "username": username
                    }
                }
            },
            "pathParameters": path_params or {},
            "queryStringParameters": query_params or {},
            "headers": {"authorization": "Bearer test-token"}
        }
        if body:
            event["body"] = json.dumps(body) if isinstance(body, dict) else body
        return event
