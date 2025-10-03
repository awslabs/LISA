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
from unittest.mock import Mock, patch
from types import SimpleNamespace


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
