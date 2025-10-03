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

"""Refactored repository lambda tests demonstrating improved isolation."""

import json
import os
import sys
import urllib.parse
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from moto import mock_aws
from models.domain_objects import IngestionJob, IngestionStatus

# Import the test helper from conftest
from conftest import RepositoryTestHelper

# Set up environment before imports
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["LISA_RAG_VECTOR_STORE_TABLE"] = "vector-store-table"
os.environ["LISA_INGESTION_JOB_TABLE_NAME"] = "testing-ingestion-table"
os.environ["RAG_DOCUMENT_TABLE"] = "rag-document-table"
os.environ["RAG_SUB_DOCUMENT_TABLE"] = "rag-sub-document-table"
os.environ["BUCKET_NAME"] = "test-bucket"
os.environ["LISA_API_URL_PS_NAME"] = "test-api-url"
os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"] = "test-secret-name"
os.environ["REGISTERED_REPOSITORIES_PS"] = "test-repositories"
os.environ["REST_API_VERSION"] = "v1"

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@mock_aws()
def test_list_jobs_function_refactored(mock_admin_auth_context, mock_repositories, lambda_context):
    """Test the list_jobs function - REFACTORED VERSION.
    
    This test demonstrates the improved approach:
    - Uses fixtures instead of global mocks
    - No manual cleanup required
    - Clear, isolated test setup
    """
    from repository.lambda_functions import list_jobs
    
    # Create test data - IngestionJob objects
    job1 = IngestionJob(
        id="job-1",
        repository_id="test-repo",
        collection_id="test-collection",
        status=IngestionStatus.INGESTION_COMPLETED,
        username="admin-user",
        s3_path="s3://bucket/doc1.pdf"
    )
    job2 = IngestionJob(
        id="job-2",
        repository_id="test-repo",
        collection_id="test-collection",
        status=IngestionStatus.INGESTION_IN_PROGRESS,
        username="admin-user",
        s3_path="s3://bucket/doc2.pdf"
    )
    job3 = IngestionJob(
        id="job-3",
        repository_id="test-repo",
        collection_id="test-collection",
        status=IngestionStatus.INGESTION_FAILED,
        username="admin-user",
        s3_path="s3://bucket/doc3.pdf"
    )
    
    # Configure repository mock to return jobs
    mock_repositories["job_repo"].list_jobs_by_repository.return_value = (
        [job1, job2, job3], 
        None  # No pagination key
    )
    
    # Create event using helper
    event = RepositoryTestHelper.create_admin_event(repository_id="test-repo")
    
    # Execute function
    result = list_jobs(event, lambda_context)
    
    # Verify response structure
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    
    # Verify ListJobsResponse format
    assert "jobs" in body
    assert "lastEvaluatedKey" in body
    assert "hasNextPage" in body
    assert "hasPreviousPage" in body
    
    # Verify job data
    assert len(body["jobs"]) == 3
    assert body["hasNextPage"] is False
    assert body["hasPreviousPage"] is False
    assert body["lastEvaluatedKey"] is None
    
    # Verify repository method was called correctly
    mock_repositories["job_repo"].list_jobs_by_repository.assert_called_once_with(
        repository_id="test-repo",
        username="admin-user",
        is_admin=True,
        time_limit_hours=720,  # Default 30 days
        page_size=10,  # Default page size
        last_evaluated_key=None
    )


@mock_aws()
def test_list_jobs_with_pagination_refactored(mock_admin_auth_context, mock_repositories, lambda_context):
    """Test list_jobs function with pagination parameters - REFACTORED VERSION.
    
    Demonstrates how custom query parameters are handled.
    """
    from repository.lambda_functions import list_jobs
    
    # Create test data
    job1 = IngestionJob(
        id="job-1",
        repository_id="test-repo",
        collection_id="test-collection",
        status=IngestionStatus.INGESTION_COMPLETED,
        username="admin-user",
        s3_path="s3://bucket/doc1.pdf"
    )
    
    # Configure mock with pagination response
    last_evaluated_key = {
        "id": "job-1",
        "repository_id": "test-repo",
        "created_date": "2025-09-25T19:14:16.404128+00:00"
    }
    mock_repositories["job_repo"].list_jobs_by_repository.return_value = (
        [job1],
        last_evaluated_key
    )
    
    # Create event with pagination parameters
    event = RepositoryTestHelper.create_admin_event(
        repository_id="test-repo",
        queryStringParameters={"pageSize": "5", "timeLimit": "48"}
    )
    
    # Execute function
    result = list_jobs(event, lambda_context)
    
    # Verify response
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    
    # Verify pagination response
    assert len(body["jobs"]) == 1
    assert body["hasNextPage"] is True  # Has more pages
    assert body["hasPreviousPage"] is False  # First page
    assert body["lastEvaluatedKey"] == last_evaluated_key
    
    # Verify custom parameters were used
    mock_repositories["job_repo"].list_jobs_by_repository.assert_called_once_with(
        repository_id="test-repo",
        username="admin-user",
        is_admin=True,
        time_limit_hours=48,  # Custom time limit
        page_size=5,  # Custom page size
        last_evaluated_key=None
    )


@mock_aws()
def test_list_jobs_with_last_evaluated_key_refactored(mock_admin_auth_context, mock_repositories, lambda_context):
    """Test list_jobs function with lastEvaluatedKey parameter - REFACTORED VERSION.
    
    Demonstrates pagination continuation with lastEvaluatedKey.
    """
    from repository.lambda_functions import list_jobs
    
    # Create test data
    job2 = IngestionJob(
        id="job-2",
        repository_id="test-repo",
        collection_id="test-collection",
        status=IngestionStatus.INGESTION_IN_PROGRESS,
        username="admin-user",
        s3_path="s3://bucket/doc2.pdf"
    )
    
    # Configure mock - no more pages after this
    mock_repositories["job_repo"].list_jobs_by_repository.return_value = ([job2], None)
    
    # Create lastEvaluatedKey (URL-encoded)
    last_evaluated_key_json = json.dumps({
        "id": "job-1",
        "repository_id": "test-repo",
        "created_date": "2025-09-25T19:14:16.404128+00:00"
    })
    encoded_key = urllib.parse.quote(last_evaluated_key_json)
    
    # Create event with lastEvaluatedKey
    event = RepositoryTestHelper.create_admin_event(
        repository_id="test-repo",
        queryStringParameters={"lastEvaluatedKey": encoded_key}
    )
    
    # Execute function
    result = list_jobs(event, lambda_context)
    
    # Verify response
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    
    # Verify pagination state
    assert len(body["jobs"]) == 1
    assert body["hasNextPage"] is False  # No more pages
    assert body["hasPreviousPage"] is True  # Has previous pages
    assert body["lastEvaluatedKey"] is None
    
    # Verify lastEvaluatedKey was parsed and passed correctly
    expected_key = json.loads(last_evaluated_key_json)
    mock_repositories["job_repo"].list_jobs_by_repository.assert_called_once_with(
        repository_id="test-repo",
        username="admin-user",
        is_admin=True,
        time_limit_hours=720,  # Default
        page_size=10,  # Default
        last_evaluated_key=expected_key
    )


@mock_aws()
def test_list_jobs_empty_results_refactored(mock_admin_auth_context, mock_repositories, lambda_context):
    """Test list_jobs with no results - REFACTORED VERSION.
    
    Demonstrates testing edge cases with fixtures.
    """
    from repository.lambda_functions import list_jobs
    
    # Configure mock to return empty results
    mock_repositories["job_repo"].list_jobs_by_repository.return_value = ([], None)
    
    # Create event
    event = RepositoryTestHelper.create_admin_event(repository_id="test-repo")
    
    # Execute function
    result = list_jobs(event, lambda_context)
    
    # Verify response
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    
    # Verify empty response structure
    assert len(body["jobs"]) == 0
    assert body["hasNextPage"] is False
    assert body["hasPreviousPage"] is False
    assert body["lastEvaluatedKey"] is None
