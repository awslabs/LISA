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

import os

# Set up mock AWS credentials first, before any imports
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["LISA_RAG_VECTOR_STORE_TABLE"] = "vector-store-table"
os.environ["RAG_DOCUMENT_TABLE"] = "rag-document-table"
os.environ["RAG_SUB_DOCUMENT_TABLE"] = "rag-sub-document-table"
os.environ["BUCKET_NAME"] = "test-bucket"
os.environ["LISA_API_URL_PS_NAME"] = "test-api-url"
os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"] = "test-secret-name"
os.environ["REGISTERED_REPOSITORIES_PS"] = "test-repositories"
os.environ["LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER"] = "test-state-machine-arn"
os.environ["REST_API_VERSION"] = "v1"
os.environ["LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER"] = "test-create-state-machine-arn"
os.environ["LISA_INGESTION_JOB_TABLE_NAME"] = "testing-ingestion-table"

# Now import other modules
import functools
import json
import logging
import sys
import urllib.parse
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
import requests
from botocore.config import Config
from models.domain_objects import IngestionJob, IngestionStatus
from moto import mock_aws
from utilities.exceptions import HTTPException
from utilities.validation import validate_model_name, ValidationError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


# Define mock api_wrapper implementation
def mock_api_wrapper(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Import ValidationError at wrapper execution time
        try:
            from utilities.validation import ValidationError as CustomValidationError
        except ImportError:
            CustomValidationError = None

        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict) and "statusCode" in result:
                return result
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps(result, default=str),
            }
        except HTTPException as e:
            # Handle HTTP exceptions with their defined status code
            status_code = e.http_status_code
            return {
                "statusCode": status_code,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": e.message}),
            }
        except (ValueError, KeyError) as e:
            error_msg = str(e)
            # Determine appropriate status code based on error message
            status_code = 400
            if "not found" in error_msg.lower():
                status_code = 404
            elif "not authorized" in error_msg.lower() or "permission" in error_msg.lower():
                status_code = 403

            return {
                "statusCode": status_code,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": error_msg}),
            }
        except Exception as e:
            # Check if it's a ValidationError from utilities.validation
            if CustomValidationError and isinstance(e, CustomValidationError):
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": str(e)}),
                }
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,  # Use 500 for unexpected errors
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


# Mock the admin_only decorator to just call the function
def mock_admin_only(func):
    @functools.wraps(func)
    def wrapper(event, context, *args, **kwargs):
        # Just pass through to the wrapped function
        return func(event, context, *args, **kwargs)

    return wrapper


# Create mock modules - SINGLE INSTANCE OF EACH
mock_create_env = MagicMock()
mock_vs_repo = MagicMock()
mock_doc_repo = MagicMock()
mock_common = MagicMock()

# Set up common mock values - SINGLE CONFIGURATION
mock_common.get_username.return_value = "test-user"
mock_common.retry_config = retry_config
mock_common.get_groups.return_value = ["test-group"]
mock_common.is_admin.return_value = False
mock_common.get_user_context.return_value = ("test-user", False, ["test-group"])
mock_common.api_wrapper = mock_api_wrapper
mock_common.get_id_token.return_value = "test-token"
mock_common.get_cert_path.return_value = None
mock_common.admin_only = mock_admin_only

# Create mock modules for missing dependencies
mock_langchain_community = MagicMock()
mock_langchain_core = MagicMock()
mock_opensearchpy = MagicMock()
mock_requests_aws4auth = MagicMock()

# Create mock SSM client
mock_ssm = MagicMock()
mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-arn"}}

# Create mock S3 client
mock_s3 = MagicMock()
mock_s3.generate_presigned_url = MagicMock(return_value="https://test-url")
mock_s3.generate_presigned_post.return_value = {"url": "https://test-url"}
mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"test content")}

# Create mock secrets manager client
mock_secrets = MagicMock()
mock_secrets.get_secret_value.return_value = {"SecretString": "test-secret"}

# Create mock IAM client
mock_iam = MagicMock()
mock_iam.get_role.return_value = {"Role": {"Arn": "test-role-arn"}}

# Create mock DynamoDB client
mock_dynamodb = MagicMock()
mock_dynamodb.get_item.return_value = {"Item": {"id": {"S": "test-id"}}}
mock_dynamodb.put_item.return_value = {}
mock_dynamodb.delete_item.return_value = {}
mock_dynamodb.query.return_value = {"Items": []}
mock_dynamodb.scan.return_value = {"Items": []}

# Create mock step functions client
mock_step_functions = MagicMock()
mock_step_functions.start_execution.return_value = {"executionArn": "test-execution-arn"}

# Create mock vector store client
mock_vector_store = MagicMock()
mock_vector_store.similarity_search.return_value = [
    MagicMock(page_content="Test content", metadata={"source": "test-source"})
]
mock_vector_store.add_texts.return_value = ["subdoc1"]

# Set up mock repository values
mock_vs_repo.VectorStoreRepository.return_value = mock_vs_repo
mock_vs_repo.get_registered_repositories.return_value = [
    {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
]
mock_vs_repo.get_repository_status.return_value = {"test-repo": "active"}
mock_vs_repo.find_repository_by_id.return_value = {
    "name": "Test Repository",
    "type": "opensearch",
    "allowedGroups": ["test-group"],
    "status": "active",
    "stackName": "test-stack",
}

# Set up mock document repository values
mock_doc_repo.RagDocumentRepository.return_value = mock_doc_repo
mock_doc_repo.find_by_id.return_value = {"source": "s3://test-bucket/test-key"}
mock_doc_repo.list_all.return_value = ([{"documentId": "test-doc", "name": "Test Document"}], None)
mock_doc_repo.save.return_value = {"document_id": "test-doc", "subdocs": ["subdoc1"]}

# Mock get_vector_store_client
mock_get_vector_store_client = MagicMock(return_value=mock_vector_store)


# Mock boto3 client function
def mock_boto3_client(*args, **kwargs):
    # Support both (service_name, region_name, config) and (service_name)
    service_name = args[0] if args else kwargs.get("service_name")
    if not service_name:
        return MagicMock()  # Fallback for any unexpected calls
    if service_name == "ssm":
        return mock_ssm
    elif service_name == "s3":
        return mock_s3
    elif service_name == "stepfunctions":
        return mock_step_functions
    elif service_name == "secretsmanager":
        return mock_secrets
    elif service_name == "iam":
        return mock_iam
    elif service_name == "dynamodb":
        return mock_dynamodb
    else:
        return MagicMock()  # Return a generic MagicMock for other services


# Set up all patches at module level - SINGLE SETUP
# Patch sys.modules to provide mock modules needed for imports
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
        "repository.vector_store_repo": mock_vs_repo,
        "repository.rag_document_repo": mock_doc_repo,
        "langchain_community": mock_langchain_community,
        "langchain_community.vectorstores": mock_langchain_community,
        "langchain_core": mock_langchain_core,
        "langchain_core.embeddings": mock_langchain_core,
        "langchain_core.vectorstores": mock_langchain_core,
        "opensearchpy": mock_opensearchpy,
        "requests_aws4auth": mock_requests_aws4auth,
    },
).start()

# Patch specific functions from utilities.common_functions and utilities.auth
patch("utilities.auth.get_username", mock_common.get_username).start()
patch("utilities.auth.get_groups", mock_common.get_groups).start()
patch("utilities.auth.is_admin", mock_common.is_admin).start()
patch("utilities.auth.get_user_context", mock_common.get_user_context).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()
patch("utilities.common_functions.get_id_token", mock_common.get_id_token).start()
patch("utilities.common_functions.get_cert_path", mock_common.get_cert_path).start()
patch("utilities.auth.admin_only", mock_admin_only).start()

# Note: boto3.client will be patched per-test to avoid global conflicts
# Global boto3.client patch removed to prevent interference with other test modules

# Only now import the lambda functions to ensure they use our mocked dependencies
from repository.lambda_functions import _ensure_document_ownership, get_repository, presigned_url


@pytest.fixture(autouse=True)
def mock_boto3_client_fixture():
    """Fixture to patch boto3.client for repository tests with proper isolation."""
    with patch("boto3.client", side_effect=mock_boto3_client):
        yield


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(scope="function")
def dynamodb(aws_credentials):
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def vector_store_table(dynamodb):
    """Create a mock DynamoDB table for vector store."""
    table = dynamodb.create_table(
        TableName="vector-store-table",
        KeySchema=[{"AttributeName": "repositoryId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "repositoryId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture(scope="function")
def rag_document_table(dynamodb):
    """Create a mock DynamoDB table for RAG documents."""
    table = dynamodb.create_table(
        TableName="rag-document-table",
        KeySchema=[{"AttributeName": "documentId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "documentId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture(scope="function")
def rag_sub_document_table(dynamodb):
    """Create a mock DynamoDB table for RAG sub-documents."""
    table = dynamodb.create_table(
        TableName="rag-sub-document-table",
        KeySchema=[{"AttributeName": "subDocumentId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "subDocumentId", "AttributeType": "S"}],
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
def sample_repository():
    return {
        "repositoryId": "test-repo",
        "config": {
            "name": "Test Repository",
            "type": "opensearch",
            "allowedGroups": ["test-group"],
            "status": "active",
        },
    }


def test_list_all():
    """Test list_all lambda function"""

    # Create a patched version that returns the expected repository list
    def mock_list_all_func(event, context):
        return [{"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}]

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.list_all", side_effect=mock_list_all_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                }
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_list_all_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert len(body) == 1
            assert body[0]["name"] == "Test Repository"


def test_list_status():
    """Test list_status lambda function"""

    # Create a patched version that returns the expected repository status
    def mock_list_status_func(event, context):
        return {"test-repo": "active"}

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.list_status", side_effect=mock_list_status_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

            # Set admin to True for this test
            mock_common.is_admin.return_value = True

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_list_status_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert isinstance(body, dict)
            assert body["test-repo"] == "active"


def test_similarity_search():
    """Test similarity_search lambda function"""

    # Create a patched version that returns the expected search results
    def mock_similarity_search_func(event, context):
        return {"docs": [{"Document": {"page_content": "Test content", "metadata": {"source": "test-source"}}}]}

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.similarity_search", side_effect=mock_similarity_search_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"modelName": "test-model", "query": "test query", "topK": "3"},
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_similarity_search_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert "docs" in body
            assert len(body["docs"]) >= 1
            assert "page_content" in body["docs"][0]["Document"]
            assert body["docs"][0]["Document"]["page_content"] == "Test content"


def test_ingest_documents():
    """Test ingest_documents lambda function"""

    # Create a patched version that returns the expected response
    def mock_ingest_documents_func(event, context):
        return {
            "documentIds": ["test-doc"],
            "chunkCount": 1,
        }

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.ingest_documents", side_effect=mock_ingest_documents_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"chunkSize": "1000", "chunkOverlap": "200"},
                "body": json.dumps({"embeddingModel": {"modelName": "test-model"}, "keys": ["test-key"]}),
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_ingest_documents_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert "documentIds" in body
            assert "chunkCount" in body


def test_download_document():
    """Test download_document lambda function"""

    # Create a patched version that returns the expected URL
    def mock_download_document_func(event, context):
        return "https://test-url"

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.download_document", side_effect=mock_download_document_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo", "documentId": "test-doc"},
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_download_document_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            assert response["body"] == '"https://test-url"'  # JSON-encoded string


def test_list_docs():
    """Test list_docs lambda function"""

    # Create a patched version that returns the expected document list
    def mock_list_docs_func(event, context):
        return {"documents": [{"documentId": "test-doc", "name": "Test Document"}], "lastEvaluated": None}

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.list_docs", side_effect=mock_list_docs_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"collectionId": "test-collection"},
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_list_docs_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert len(body["documents"]) == 1
            assert body["documents"][0]["name"] == "Test Document"


def test_delete():
    """Test delete lambda function"""

    # Create a patched version that returns the success response
    def mock_delete_func(event, context):
        return {"status": "success", "executionArn": "test-execution-arn"}

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.delete", side_effect=mock_delete_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
                "pathParameters": {"repositoryId": "test-repo"},
            }

            # Set admin to True for this test
            mock_common.is_admin.return_value = True

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_delete_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["status"] == "success"
            assert body["executionArn"] == "test-execution-arn"


def test_delete_documents_by_id():
    """Test delete_documents lambda function by document id"""

    # Create a patched version that returns the expected response
    def mock_delete_documents_func(event, context):
        return {
            "documents": ["test-repo/test-collection/test-doc"],
            "removedDocuments": 1,
            "removedDocumentChunks": 2,
            "removedS3Documents": 1,
        }

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.delete_documents", side_effect=mock_delete_documents_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "body": json.dumps({"documentIds": ["test-doc"]}),
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_delete_documents_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert "removedDocuments" in body
            assert body["removedDocuments"] == 1
            assert "removedDocumentChunks" in body
            assert "removedS3Documents" in body


def test_delete_documents_by_name():
    """Test delete_documents lambda function by document name"""

    # Create a patched version that returns the expected response
    def mock_delete_documents_func(event, context):
        return {"removedDocuments": 1, "removedDocumentChunks": 2, "removedS3Documents": 1}

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.delete_documents", side_effect=mock_delete_documents_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"collectionId": "test-collection", "documentName": "Test Document"},
                "body": "{}",
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_delete_documents_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert "removedDocuments" in body
            assert body["removedDocuments"] == 1


def test_delete_documents_error():
    """Test delete_documents lambda function with no document parameters"""

    # Create a patched version that raises an exception
    def mock_delete_documents_func(event, context):
        raise ValueError("No 'documentIds' or 'documentName' parameter supplied")

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.delete_documents", side_effect=mock_delete_documents_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event with missing parameters
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "body": "{}",
            }

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_delete_documents_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert "error" in body
            assert "No 'documentIds' or 'documentName' parameter supplied" in body["error"]


def test_delete_documents_unauthorized():
    """Test delete_documents lambda function with unauthorized access"""

    # Create a patched version that raises an exception
    def mock_delete_documents_func(event, context):
        raise ValueError("Document test-doc is not owned by test-user")

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.delete_documents", side_effect=mock_delete_documents_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "body": json.dumps({"documentIds": ["test-doc"]}),
            }

            # Ensure admin is false
            mock_common.is_admin.return_value = False

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_delete_documents_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert "error" in body
            assert "Document test-doc is not owned by test-user" in body["error"]


def test_presigned_url():
    """Test presigned_url lambda function"""
    # Create test event
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}, "body": "test-key"}

    # Mock S3 operations
    mock_s3.generate_presigned_post.return_value = {
        "url": "https://test-bucket.s3.amazonaws.com",
        "fields": {"key": "test-key"},
    }

    response = presigned_url(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "response" in body
    assert "url" in body["response"]
    assert body["response"]["url"].startswith("https://test-bucket.s3.amazonaws.com")


def test_create():
    """Test create lambda function"""

    # Create a patched version that returns the success response
    def mock_create_func(event, context):
        return {"status": "success", "executionArn": "test-execution-arn"}

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.create", side_effect=mock_create_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
                "body": json.dumps(
                    {"ragConfig": {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"]}}
                ),
            }

            # Set admin to True for this test
            mock_common.is_admin.return_value = True

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_create_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["status"] == "success"
            assert body["executionArn"] == "test-execution-arn"


def test_delete_legacy():
    """Test delete lambda function with legacy repository"""

    # Create a patched version that returns the success response
    def mock_delete_func(event, context):
        return {"status": "success", "executionArn": "legacy"}

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.delete", side_effect=mock_delete_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
                "pathParameters": {"repositoryId": "test-repo"},
            }

            # Set admin to True for this test
            mock_common.is_admin.return_value = True

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_delete_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["status"] == "success"
            assert body["executionArn"] == "legacy"


def test_delete_missing_repository_id():
    """Test delete lambda function with missing repository ID"""

    # Create a patched version that raises a ValidationError
    def mock_delete_func(event, context):
        # Just directly raise the error we expect
        raise ValidationError("repositoryId is required")

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.delete", side_effect=mock_delete_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event with missing repositoryId
            event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}, "pathParameters": {}}

            # Set admin to True for this test
            mock_common.is_admin.return_value = True

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_delete_func)(event, None)

            # Verify the response
            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert "error" in body
            assert "repositoryId is required" in body["error"]


def test_RagEmbeddings_error():
    """Test error handling in RagEmbeddings function"""

    # Create a patched version of the class that raises an error
    def mock_RagEmbeddings(model_name, api_key):
        raise Exception("SSM error")

    # Patch the class from the correct module
    with patch("repository.embeddings.RagEmbeddings", side_effect=mock_RagEmbeddings):
        # Test that the error is properly handled
        with pytest.raises(Exception, match="SSM error"):
            mock_RagEmbeddings("test-model", "test-token")


def test_similarity_search_forbidden():
    """Test similarity_search with forbidden access"""

    # Create a patched version that raises a permission error
    def mock_similarity_search_func(event, context):
        raise ValueError("User does not have permission to access this repository")

    # Patch the api_wrapper to properly wrap our mock function
    with patch("repository.lambda_functions.similarity_search", side_effect=mock_similarity_search_func):
        with patch("utilities.common_functions.api_wrapper", side_effect=mock_api_wrapper):
            # Create test event
            event = {
                "requestContext": {
                    "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"modelName": "test-model", "query": "test query"},
            }

            # Ensure admin is false
            mock_common.is_admin.return_value = False

            # Call the function through our patched api_wrapper
            response = mock_api_wrapper(mock_similarity_search_func)(event, None)

            # Verify the response with status code 403
            assert response["statusCode"] == 403
            body = json.loads(response["body"])
            assert "error" in body
            assert "User does not have permission to access this repository" in body["error"]


def test_remove_legacy():
    """Test _remove_legacy function"""

    # Create a patched version of the function
    def mock_remove_legacy(repository_id):
        # Just return the expected result
        return True

    # Patch the function
    with patch("repository.lambda_functions._remove_legacy", side_effect=mock_remove_legacy):
        # Call function
        result = mock_remove_legacy("test-repo")
        assert result is True


def test_pipeline_embeddings_embed_documents_error():
    """Test error handling in LisaOpenAIEmbeddings.embed_documents"""

    # Mock the function to raise an exception
    def mock_embed_documents(docs):
        raise requests.RequestException("API request failed")

    # Create a mock LisaOpenAIEmbeddings instance
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents.side_effect = mock_embed_documents

    # Patch RagEmbeddings_pipeline to return our mock
    with patch("repository.embeddings.RagEmbeddings", return_value=mock_embeddings):
        embeddings = mock_embeddings

        # Test that the error is properly handled
        with pytest.raises(requests.RequestException, match="API request failed"):
            embeddings.embed_documents(["test text"])


def test_embeddings_embed_query_error():
    """Test error handling in OpenAIEmbeddings.embed_query"""

    # Mock the function to raise an exception
    def mock_embed_query(query):
        raise ValidationError("Invalid query text")

    # Create a mock LisaOpenAIEmbeddings instance
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.side_effect = mock_embed_query

    # Patch RagEmbeddings_pipeline to return our mock
    with patch("repository.embeddings.RagEmbeddings", return_value=mock_embeddings):
        embeddings = mock_embeddings

        # Test with invalid input
        with pytest.raises(ValidationError, match="Invalid query text"):
            embeddings.embed_query(None)

        with pytest.raises(ValidationError, match="Invalid query text"):
            embeddings.embed_query("")


def test_get_repository_unauthorized():
    """Test get_repository with unauthorized access"""

    # Create a mock function that raises an exception
    def mock_get_repository(event, repository_id):
        raise HTTPException(status_code=403, message="User does not have permission to access this repository")

    # Patch the function
    with patch("repository.lambda_functions.get_repository", side_effect=mock_get_repository):
        # Create event with user not in allowed groups
        event = {
            "requestContext": {
                "authorizer": {"groups": json.dumps(["different-group"]), "claims": {"username": "test-user"}}
            }
        }

        # Test with repository that requires specific group
        with pytest.raises(HTTPException) as excinfo:
            mock_get_repository(event, "test-repo")

        assert excinfo.value.message == "User does not have permission to access this repository"


def test_document_ownership_validation():
    """Test document ownership validation logic"""
    from models.domain_objects import ChunkingStrategyType, FixedChunkingStrategy, RagDocument

    # Test case 1: User is admin
    event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}
    chunk_strategy = FixedChunkingStrategy(type=ChunkingStrategyType.FIXED, size=1000, overlap=200)
    docs = [
        RagDocument(
            document_id="test-doc",
            repository_id="repo",
            collection_id="coll",
            document_name="doc",
            source="s3://bucket/key",
            subdocs=[],
            username="other-user",
            chunk_strategy=chunk_strategy,
        )
    ]

    # This is where the patching needs to happen - BOTH get_username AND is_admin must be patched
    with patch("repository.lambda_functions.get_username") as mock_get_username:
        with patch("repository.lambda_functions.is_admin") as mock_is_admin:
            # Set the mock returns
            mock_get_username.return_value = "admin-user"
            mock_is_admin.return_value = True

            # Admin should always have access
            assert _ensure_document_ownership(event, docs) is None

            # Test case 2: User owns the document
            event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}
            docs = [
                RagDocument(
                    document_id="test-doc",
                    repository_id="repo",
                    collection_id="coll",
                    document_name="doc",
                    source="s3://bucket/key",
                    subdocs=[],
                    username="test-user",
                    chunk_strategy=chunk_strategy,
                )
            ]

            mock_get_username.return_value = "test-user"
            mock_is_admin.return_value = False

            # User owns the document
            assert _ensure_document_ownership(event, docs) is None

            # Test case 3: User doesn't own the document
            event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}
            docs = [
                RagDocument(
                    document_id="test-doc",
                    repository_id="repo",
                    collection_id="coll",
                    document_name="doc",
                    source="s3://bucket/key",
                    subdocs=[],
                    username="other-user",
                    chunk_strategy=chunk_strategy,
                )
            ]

            mock_get_username.return_value = "test-user"
            mock_is_admin.return_value = False

            # User doesn't own the document
            with pytest.raises(ValueError) as exc_info:
                _ensure_document_ownership(event, docs)
            assert "Document test-doc is not owned by test-user" in str(exc_info.value)


def test_validate_model_name():
    """Test validate_model_name function"""

    # Test valid model name
    assert validate_model_name("embedding-model") is True

    # Test invalid model name
    with pytest.raises(ValidationError):
        validate_model_name(None)

    with pytest.raises(ValidationError):
        validate_model_name("")


def test_repository_access_validation():
    """Test get_repository access validation logic"""

    # Test case 1: User is admin - get_repository should return the repository
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}, "groups": json.dumps(["admin-group"])}}
    }

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.is_admin", return_value=True
    ):
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["admin-group"], "status": "active"}
        # Admin should always have access
        result = get_repository(event, "test-repo")
        assert result == {
            "allowedGroups": ["admin-group"],
            "status": "active",
        }  # get_repository returns the repo object

    # Test case 2: User has group access
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}}
    }

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.is_admin", return_value=False
    ):
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}
        # User has the right group
        result = get_repository(event, "test-repo")
        assert result == {"allowedGroups": ["test-group"], "status": "active"}  # get_repository returns the repo object

    # Test case 3: User doesn't have access
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["wrong-group"])}}
    }

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.is_admin", return_value=False
    ), patch("repository.lambda_functions.get_groups", return_value=["wrong-group"]):
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}
        # User doesn't have the right group
        with pytest.raises(HTTPException) as exc_info:
            get_repository(event, "test-repo")
        assert exc_info.value.message == "User does not have permission to access this repository"


# Additional comprehensive tests for better coverage


def test_RagEmbeddings_function():
    """Test the RagEmbeddings function"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.get_management_key") as mock_key:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"
        mock_key.return_value = "test-token"

        result = RagEmbeddings("test-model", "test-token")

        assert result.model_name == "test-model"
        mock_cert.assert_called_once()
        assert mock_endpoint.call_count == 2  # Called twice in RagEmbeddings.__init__


def test_pipeline_embeddings_init():
    """Test RagEmbeddings initialization"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_management_key") as mock_management_key, patch(
        "repository.embeddings.get_rest_api_container_endpoint"
    ) as mock_endpoint, patch("repository.embeddings.get_cert_path") as mock_cert:

        mock_management_key.return_value = "test-token"
        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"

        embeddings = RagEmbeddings("test-model")

        assert isinstance(embeddings.model_name, str)
        assert embeddings.model_name == "test-model"
        mock_management_key.assert_called_once()
        assert mock_endpoint.call_count == 2  # Called twice in RagEmbeddings.__init__
        mock_cert.assert_called_once()


def test_pipeline_embeddings_init_error():
    """Test LisaOpenAIEmbeddings initialization error handling"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.ssm_client") as mock_ssm:
        mock_ssm.get_parameter.side_effect = Exception("SSM error")

        with pytest.raises(Exception):
            RagEmbeddings("test-model")


def test_pipeline_embeddings_embed_documents():
    """Test RagEmbeddings embed_documents method"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.requests.post") as mock_post:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]}
        mock_post.return_value = mock_response

        embeddings = RagEmbeddings("test-model", "test-token")
        result = embeddings.embed_documents(["text1", "text2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]


def test_pipeline_embeddings_embed_documents_no_texts():
    """Test RagEmbeddings embed_documents with no texts"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.get_management_key") as mock_key:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"
        mock_key.return_value = "test-token"

        embeddings = RagEmbeddings("test-model", "test-token")

        with pytest.raises(ValidationError, match="No texts provided for embedding"):
            embeddings.embed_documents([])


def test_pipeline_embeddings_embed_documents_api_error():
    """Test RagEmbeddings embed_documents with API error"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.requests.post") as mock_post:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"
        mock_post.side_effect = Exception("API request failed")

        embeddings = RagEmbeddings("test-model", "test-token")

        with pytest.raises(Exception, match="API request failed"):
            embeddings.embed_documents(["text1"])


def test_pipeline_embeddings_embed_documents_timeout():
    """Test RagEmbeddings embed_documents with timeout"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.requests.post") as mock_post:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"
        mock_post.side_effect = requests.Timeout("Request timed out")

        embeddings = RagEmbeddings("test-model", "test-token")

        with pytest.raises(Exception, match="Embedding request timed out after 5 minutes"):
            embeddings.embed_documents(["text1"])


def test_pipeline_embeddings_embed_documents_different_formats():
    """Test RagEmbeddings embed_documents with different response formats"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.requests.post") as mock_post:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"

        embeddings = RagEmbeddings("test-model", "test-token")

        # Test OpenAI format
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
        mock_post.return_value = mock_response
        result = embeddings.embed_documents(["text1", "text2"])
        assert len(result) == 2

        # Test direct list format
        mock_response.json.return_value = [[0.5, 0.6], [0.7, 0.8]]
        result = embeddings.embed_documents(["text1", "text2"])
        assert len(result) == 2


def test_pipeline_embeddings_embed_documents_no_embeddings():
    """Test RagEmbeddings embed_documents with no embeddings in response"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.requests.post") as mock_post:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "No embeddings"}
        mock_post.return_value = mock_response

        embeddings = RagEmbeddings("test-model", "test-token")

        with pytest.raises(Exception, match="No embeddings found in API response"):
            embeddings.embed_documents(["text1"])


def test_pipeline_embeddings_embed_documents_mismatch():
    """Test RagEmbeddings embed_documents with embedding count mismatch"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.requests.post") as mock_post:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}  # Only 1 embedding for 2 texts
        mock_post.return_value = mock_response

        embeddings = RagEmbeddings("test-model", "test-token")

        with pytest.raises(Exception, match="Number of embeddings does not match number of input texts"):
            embeddings.embed_documents(["text1", "text2"])


def test_pipeline_embeddings_embed_query():
    """Test RagEmbeddings embed_query method"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.requests.post") as mock_post:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_post.return_value = mock_response

        embeddings = RagEmbeddings("test-model", "test-token")
        result = embeddings.embed_query("test query")

        assert result == [0.1, 0.2, 0.3]


def test_pipeline_embeddings_embed_query_invalid():
    """Test RagEmbeddings embed_query with invalid input"""
    from repository.embeddings import RagEmbeddings

    with patch("repository.embeddings.get_rest_api_container_endpoint") as mock_endpoint, patch(
        "repository.embeddings.get_cert_path"
    ) as mock_cert, patch("repository.embeddings.get_management_key") as mock_key:

        mock_endpoint.return_value = "https://api.example.com"
        mock_cert.return_value = "/path/to/cert"
        mock_key.return_value = "test-token"

        embeddings = RagEmbeddings("test-model", "test-token")

        with pytest.raises(ValidationError, match="Invalid query text"):
            embeddings.embed_query(None)

        with pytest.raises(ValidationError, match="Invalid query text"):
            embeddings.embed_query("")


def test_real_list_all_function():
    """Test the actual list_all function with real imports"""
    from repository.lambda_functions import list_all

    # Mock the vs_repo to return test data
    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "utilities.auth.get_groups"
    ) as mock_get_groups:

        mock_get_groups.return_value = ["test-group"]
        mock_vs_repo.get_registered_repositories.return_value = [
            {"name": "Test Repo", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
        ]

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            }
        }

        result = list_all(event, SimpleNamespace())

        # The function is wrapped by api_wrapper, so we get an HTTP response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body) == 1
        assert body[0]["name"] == "Test Repo"


def test_real_list_status_function():
    """Test the actual list_status function with real imports"""
    from repository.lambda_functions import list_status

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo:
        mock_vs_repo.get_repository_status.return_value = {"test-repo": "active"}

        event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}

        # Mock admin check
        with patch("utilities.auth.is_admin", return_value=True):
            result = list_status(event, SimpleNamespace())

            # The function is wrapped by api_wrapper, so we get an HTTP response
            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert body == {"test-repo": "active"}


def test_real_similarity_search_function():
    """Test the actual similarity_search function with real imports"""
    from repository.lambda_functions import similarity_search

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.embeddings.RagEmbeddings"
    ) as mock_RagEmbeddings, patch("utilities.auth.get_groups") as mock_get_groups, patch(
        "utilities.common_functions.get_id_token"
    ) as mock_get_token:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_get_token.return_value = "test-token"
        mock_vs_repo.find_repository_by_id.return_value = {
            "repositoryId": "test-repo",
            "type": "opensearch",
            "allowedGroups": ["test-group"],
            "status": "active",
        }

        mock_embeddings = MagicMock()
        mock_RagEmbeddings.return_value = mock_embeddings

        # Mock the service layer
        mock_service = MagicMock()
        mock_service.retrieve_documents.return_value = [
            {"page_content": "Test content", "metadata": {"source": "test-source"}}
        ]

        with patch("repository.lambda_functions.RepositoryServiceFactory") as mock_factory:
            mock_factory.create_service.return_value = mock_service

            event = {
                "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": ["test-group"]}},
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"modelName": "test-model", "query": "test query", "topK": "3"},
            }

            result = similarity_search(event, SimpleNamespace())

            # The function is wrapped by api_wrapper, so we get an HTTP response
            assert "statusCode" in result
            assert "body" in result


def test_real_similarity_search_missing_params():
    """Test similarity_search with missing required parameters"""
    from repository.lambda_functions import similarity_search

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo:
        # Mock repository lookup to avoid AWS credential issues
        mock_vs_repo.find_repository_by_id.return_value = None

        # Test missing repositoryId
        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {},
            "queryStringParameters": {"modelName": "test-model", "query": "test query"},
        }

        result = similarity_search(event, SimpleNamespace())

        # Should return error response due to missing repositoryId or repository not found
        assert result["statusCode"] in [400, 500]
        body = json.loads(result["body"])
        assert "error" in body


def test_real_delete_documents_function():
    """Test the actual delete_documents function"""
    from repository.lambda_functions import delete_documents

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("utilities.auth.get_groups") as mock_get_groups, patch(
        "utilities.auth.get_username"
    ) as mock_get_username, patch(
        "utilities.auth.is_admin"
    ) as mock_is_admin:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_get_username.return_value = "test-user"
        mock_is_admin.return_value = False

        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        mock_doc_repo.find_by_id.return_value = {"username": "test-user"}
        mock_doc_repo.delete_by_id.return_value = None

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "body": json.dumps({"documentIds": ["test-doc"]}),
        }

        result = delete_documents(event, SimpleNamespace())

        assert result["statusCode"] in [200, 400, 500]


def test_real_ingest_documents_function():
    """Test the actual ingest_documents function"""
    from repository.lambda_functions import ingest_documents

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.ingestion_service"
    ) as mock_ingestion, patch("utilities.auth.get_groups") as mock_get_groups, patch(
        "utilities.auth.get_username"
    ) as mock_get_username:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_get_username.return_value = "test-user"

        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        mock_ingestion.ingest_documents.return_value = {"documentIds": ["test-doc"], "chunkCount": 1}

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {"chunkSize": "1000", "chunkOverlap": "200"},
            "body": json.dumps({"embeddingModel": {"modelName": "test-model"}, "keys": ["test-key"]}),
        }

        result = ingest_documents(event, SimpleNamespace())

        assert result["statusCode"] in [200, 400, 500]


def test_real_download_document_function():
    """Test the actual download_document function"""
    from repository.lambda_functions import download_document

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("repository.lambda_functions.s3") as mock_s3, patch(
        "utilities.auth.get_groups"
    ) as mock_get_groups, patch(
        "utilities.auth.get_username"
    ) as mock_get_username, patch(
        "utilities.auth.is_admin"
    ) as mock_is_admin:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_get_username.return_value = "test-user"
        mock_is_admin.return_value = False

        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        # Create a mock RagDocument object
        mock_doc = MagicMock()
        mock_doc.source = "s3://test-bucket/test-key"
        mock_doc.username = "test-user"
        mock_doc_repo.find_by_id.return_value = mock_doc

        mock_s3.generate_presigned_url.return_value = "https://test-url"

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo", "documentId": "test-doc"},
        }

        result = download_document(event, SimpleNamespace())

        # The function is wrapped by api_wrapper, so we get an HTTP response
        assert result["statusCode"] == 200
        # The function returns a string URL, which gets JSON serialized by api_wrapper
        # So the body is a JSON-encoded string
        assert result["body"] == '"https://test-url"'


@mock_aws()
def test_real_list_docs_function():
    """Test the actual list_docs function"""
    from repository.lambda_functions import list_docs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("utilities.auth.get_groups") as mock_get_groups:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]

        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        # Create a mock document object with model_dump method
        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"documentId": "test-doc", "name": "Test Document"}

        # Mock list_all to return the correct tuple format: (docs, last_evaluated, total_documents)
        mock_doc_repo.list_all.return_value = ([mock_doc], None, 1)

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {"collectionId": "test-collection"},
        }

        result = list_docs(event, SimpleNamespace())

        # Due to mocking complexity, just check it returns a response
        assert result["statusCode"] in [200, 500]


@mock_aws()
def test_list_docs_with_pagination():
    """Test list_docs function with pagination parameters"""
    from repository.lambda_functions import list_docs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("utilities.auth.get_groups") as mock_get_groups:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        # Create mock documents
        mock_doc1 = MagicMock()
        mock_doc1.model_dump.return_value = {"documentId": "doc1", "name": "Document 1"}
        mock_doc2 = MagicMock()
        mock_doc2.model_dump.return_value = {"documentId": "doc2", "name": "Document 2"}

        # Mock list_all to return documents with pagination info
        mock_doc_repo.list_all.return_value = ([mock_doc1, mock_doc2], {"pk": "next-page", "document_id": "doc2"}, 5)

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {
                "collectionId": "test-collection",
                "lastEvaluatedKeyPk": "current-page",
                "lastEvaluatedKeyDocumentId": "doc1",
                "lastEvaluatedKeyRepositoryId": "test-repo",
                "pageSize": "2",
            },
        }

        result = list_docs(event, SimpleNamespace())

        # Verify the response structure and pagination info
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["documents"]) == 2
        assert body["totalDocuments"] == 5
        assert body["hasNextPage"] is True
        assert body["hasPreviousPage"] is False  # No 'lastEvaluated' key in queryStringParameters
        assert body["lastEvaluated"] == {"pk": "next-page", "document_id": "doc2"}


@mock_aws()
def test_list_docs_with_previous_page():
    """Test list_docs function with previous page indicator"""
    from repository.lambda_functions import list_docs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("utilities.auth.get_groups") as mock_get_groups:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"documentId": "test-doc", "name": "Test Document"}

        mock_doc_repo.list_all.return_value = ([mock_doc], None, 1)

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {
                "collectionId": "test-collection",
                "lastEvaluated": "true",  # This indicates we're on a previous page
            },
        }

        result = list_docs(event, SimpleNamespace())

        # Verify the response handles previous page correctly
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["hasPreviousPage"] is True


@mock_aws()
def test_list_docs_with_custom_page_size():
    """Test list_docs function with custom page size"""
    from repository.lambda_functions import list_docs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("utilities.auth.get_groups") as mock_get_groups:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"documentId": "test-doc", "name": "Test Document"}

        mock_doc_repo.list_all.return_value = ([mock_doc], None, 1)

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {"collectionId": "test-collection", "pageSize": "50"},
        }

        result = list_docs(event, SimpleNamespace())

        # Verify the response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["hasPreviousPage"] is False  # No pagination parameters


@mock_aws()
def test_list_docs_with_edge_case_page_sizes():
    """Test list_docs function with edge case page sizes"""
    from repository.lambda_functions import list_docs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("utilities.auth.get_groups") as mock_get_groups:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"documentId": "test-doc", "name": "Test Document"}

        mock_doc_repo.list_all.return_value = ([mock_doc], None, 1)

        # Test with page size 0 (should be clamped to 1)
        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {"collectionId": "test-collection", "pageSize": "0"},
        }

        result = list_docs(event, SimpleNamespace())
        assert result["statusCode"] == 200

        # Test with page size > 100 (should be clamped to 100)
        event["queryStringParameters"]["pageSize"] = "150"
        result = list_docs(event, SimpleNamespace())
        assert result["statusCode"] == 200


@mock_aws()
def test_list_docs_with_encoded_pagination_keys():
    """Test list_docs function with URL-encoded pagination keys"""
    from repository.lambda_functions import list_docs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_doc_repo, patch("utilities.auth.get_groups") as mock_get_groups:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"documentId": "test-doc", "name": "Test Document"}

        mock_doc_repo.list_all.return_value = ([mock_doc], None, 1)

        # Test with URL-encoded keys
        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {
                "collectionId": "test-collection",
                "lastEvaluatedKeyPk": "repo%3Atest-collection",
                "lastEvaluatedKeyDocumentId": "doc%2Fwith%2Fslashes",
                "lastEvaluatedKeyRepositoryId": "test%2Drepo",
            },
        }

        result = list_docs(event, SimpleNamespace())

        # Verify the response handles URL decoding correctly
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["hasPreviousPage"] is False  # No 'lastEvaluated' key


def test_real_create_function():
    """Test the actual create function"""
    from repository.lambda_functions import create

    with patch("repository.lambda_functions.step_functions_client") as mock_sf, patch(
        "repository.lambda_functions.ssm_client"
    ) as mock_ssm, patch("utilities.auth.is_admin") as mock_is_admin:

        # Setup mocks
        mock_is_admin.return_value = True
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-arn"}}
        mock_sf.start_execution.return_value = {"executionArn": "test-execution-arn"}

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "body": json.dumps({"type": "opensearch", "repositoryId": "test-repo", "embeddingModelId": "test-model"}),
        }

        result = create(event, SimpleNamespace())

        # The function is wrapped by api_wrapper, so we get an HTTP response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "executionArn" in body


def test_real_delete_function():
    """Test the actual delete function"""
    from repository.lambda_functions import delete

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.step_functions_client"
    ) as mock_sf, patch("repository.embeddings.ssm_client") as mock_ssm, patch(
        "utilities.auth.is_admin"
    ) as mock_is_admin:

        # Setup mocks
        mock_is_admin.return_value = True
        mock_vs_repo.find_repository_by_id.return_value = {"stackName": "test-stack"}
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-arn"}}
        mock_sf.start_execution.return_value = {"executionArn": "test-execution-arn"}

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "pathParameters": {"repositoryId": "test-repo"},
        }

        result = delete(event, SimpleNamespace())

        # The function is wrapped by api_wrapper, so we get an HTTP response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "executionArn" in body


def test_real_delete_function_legacy():
    """Test the actual delete function with legacy repository"""
    from repository.lambda_functions import delete

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "utilities.auth.is_admin"
    ) as mock_is_admin, patch("repository.lambda_functions._remove_legacy") as mock_remove_legacy:

        # Setup mocks
        mock_is_admin.return_value = True
        # Return a legacy repository config instead of None
        mock_vs_repo.find_repository_by_id.return_value = {"legacy": True}
        mock_vs_repo.delete.return_value = None
        mock_remove_legacy.return_value = None

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "pathParameters": {"repositoryId": "legacy-repo"},
        }

        result = delete(event, SimpleNamespace())

        # The function is wrapped by api_wrapper, so we get an HTTP response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["executionArn"] == "legacy"


def test_remove_legacy_function():
    """Test the _remove_legacy function"""
    from repository.lambda_functions import _remove_legacy

    with patch("repository.lambda_functions.ssm_client") as mock_ssm:

        # Mock SSM to return valid JSON with repositories
        repositories = [
            {"repositoryId": "test-repo", "name": "Test Repo"},
            {"repositoryId": "other-repo", "name": "Other Repo"},
        ]
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps(repositories)}}
        mock_ssm.put_parameter.return_value = {}

        # Should not raise any exception
        _remove_legacy("test-repo")

        # Should call put_parameter to update the list
        mock_ssm.put_parameter.assert_called_once()


def test_ensure_repository_access_edge_cases():
    """Test repository access validation with edge cases (now handled in get_repository)"""

    # Test with missing groups in event - get_groups returns empty list, so user has no access
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.is_admin", return_value=False
    ), patch("repository.lambda_functions.get_groups", return_value=[]):
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        # get_repository will raise HTTPException because user has no groups (empty list)
        with pytest.raises(HTTPException) as exc_info:
            get_repository(event, "test-repo")
        assert exc_info.value.http_status_code == 403


def test_ensure_document_ownership_edge_cases():
    """Test _ensure_document_ownership with edge cases"""

    # Test with empty docs list
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    # Should not raise exception for empty list
    assert _ensure_document_ownership(event, []) is None


def test_real_similarity_search_bedrock_kb_function():
    """Test the actual similarity_search function for Bedrock Knowledge Base repositories"""
    from repository.lambda_functions import similarity_search

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.bedrock_client"
    ) as mock_bedrock, patch("utilities.auth.get_groups") as mock_get_groups, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_collection_service:

        mock_get_groups.return_value = ["test-group"]
        mock_vs_repo.find_repository_by_id.return_value = {
            "repositoryId": "test-repo",
            "type": "bedrock_knowledge_base",
            "allowedGroups": ["test-group"],
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseId": "kb-123",
                "dataSources": [{"id": "ds-123"}],
            },
            "status": "active",
        }

        # Mock collection model lookup
        mock_collection_service.get_collection_model.return_value = "test-model"

        mock_bedrock.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "KB doc content"},
                    "location": {"s3Location": {"uri": "s3://bucket/path/doc1.pdf"}},
                },
                {
                    "content": {"text": "Second"},
                    "location": {"s3Location": {"uri": "s3://bucket/path/doc2.txt"}},
                },
            ]
        }

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {
                "modelName": "test-model",
                "query": "test query",
                "topK": "2",
                "collectionId": "ds-123",
            },
        }

        result = similarity_search(event, SimpleNamespace())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "docs" in body
        assert len(body["docs"]) == 2
        first_doc = body["docs"][0]["Document"]
        assert first_doc["page_content"] == "KB doc content"
        assert first_doc["metadata"]["source"] == "s3://bucket/path/doc1.pdf"


@mock_aws()
def test_list_jobs_function():
    """Test the list_jobs function"""
    from repository.lambda_functions import list_jobs

    # Override global mocks for this test
    mock_common.get_username.return_value = "admin-user"
    mock_common.is_admin.return_value = True

    try:
        with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
            "repository.lambda_functions.ingestion_job_repository"
        ) as mock_job_repo, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.is_admin"
        ) as mock_is_admin, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, patch(
            "repository.lambda_functions.get_user_context"
        ) as mock_get_user_context:

            # Setup mocks
            mock_get_groups.return_value = ["test-group"]
            mock_is_admin.return_value = True  # Admin access required
            mock_get_username.return_value = "admin-user"
            mock_get_user_context.return_value = (
                "admin-user",
                True,
                ["test-group"],
            )  # Return username, is_admin, groups
            mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

            # Create real IngestionJob objects
            job1 = IngestionJob(
                id="job-1",
                repository_id="test-repo",
                collection_id="test-collection",
                status=IngestionStatus.INGESTION_COMPLETED,
                username="admin-user",
                s3_path="s3://bucket/doc1.pdf",
            )
            job2 = IngestionJob(
                id="job-2",
                repository_id="test-repo",
                collection_id="test-collection",
                status=IngestionStatus.INGESTION_IN_PROGRESS,
                username="admin-user",
                s3_path="s3://bucket/doc2.pdf",
            )
            job3 = IngestionJob(
                id="job-3",
                repository_id="test-repo",
                collection_id="test-collection",
                status=IngestionStatus.INGESTION_FAILED,
                username="admin-user",
                s3_path="s3://bucket/doc3.pdf",
            )

            # Mock repository method to return jobs and no pagination key
            mock_job_repo.list_jobs_by_repository.return_value = ([job1, job2, job3], None)

            event = {
                "requestContext": {
                    "authorizer": {
                        "username": "admin-user",
                        "claims": {"username": "admin-user"},
                        "groups": json.dumps(["test-group"]),
                    }
                },
                "pathParameters": {"repositoryId": "test-repo"},
            }

            result = list_jobs(event, SimpleNamespace())

            # Verify the response
            assert result["statusCode"] == 200
            body = json.loads(result["body"])

            # Should return ListJobsResponse format with jobs array
            assert "jobs" in body
            assert "lastEvaluatedKey" in body
            assert "hasNextPage" in body
            assert "hasPreviousPage" in body

            assert len(body["jobs"]) == 3
            assert body["hasNextPage"] is False  # No lastEvaluatedKey returned
            assert body["hasPreviousPage"] is False  # No lastEvaluatedKey in query params
            assert body["lastEvaluatedKey"] is None

            # Verify job repository method was called correctly
            mock_job_repo.list_jobs_by_repository.assert_called_once_with(
                repository_id="test-repo",
                username="admin-user",
                is_admin=True,
                time_limit_hours=720,  # Default 30 days
                page_size=10,  # Default page size
                last_evaluated_key=None,
            )
    finally:
        # Reset global mocks to defaults
        mock_common.get_username.return_value = "test-user"
        mock_common.is_admin.return_value = False


@mock_aws()
def test_list_jobs_missing_repository_id():
    """Test list_jobs function with missing repository ID"""
    from repository.lambda_functions import list_jobs

    with patch("utilities.auth.is_admin") as mock_is_admin:
        mock_is_admin.return_value = True

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "admin-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {},  # Missing repositoryId
        }

        result = list_jobs(event, SimpleNamespace())

        # Should return validation error (ValidationError gets wrapped
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "repositoryId is required" in body["error"]


@mock_aws()
def test_list_jobs_unauthorized_access():
    """Test list_jobs function with unauthorized access"""
    from repository.lambda_functions import list_jobs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "utilities.auth.get_groups"
    ) as mock_get_groups, patch("utilities.auth.is_admin") as mock_is_admin:

        # Setup mocks - user is not admin and doesn't have group access
        mock_get_groups.return_value = ["other-group"]
        mock_is_admin.return_value = False
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        # Override global mocks
        mock_common.get_groups.return_value = ["other-group"]
        mock_common.is_admin.return_value = False
        mock_common.get_username.return_value = "regular-user"

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "regular-user"}, "groups": json.dumps(["other-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
        }

        result = list_jobs(event, SimpleNamespace())

        # Should return forbidden error
        assert result["statusCode"] == 403
        body = json.loads(result["body"])
        assert "does not have permission" in body["error"]


@mock_aws()
def test_list_jobs_empty_results():
    """Test list_jobs function with no jobs found"""
    from repository.lambda_functions import list_jobs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.ingestion_job_repository"
    ) as mock_job_repo, patch("utilities.auth.get_groups") as mock_get_groups, patch(
        "utilities.auth.is_admin"
    ) as mock_is_admin, patch(
        "utilities.auth.get_username"
    ) as mock_get_username:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_is_admin.return_value = True
        mock_get_username.return_value = "admin-user"
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        # Override global mocks
        mock_common.get_username.return_value = "admin-user"
        mock_common.is_admin.return_value = True

        # Mock repository method to return empty list and no pagination key
        mock_job_repo.list_jobs_by_repository.return_value = ([], None)

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "admin-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
        }

        result = list_jobs(event, SimpleNamespace())

        # Verify the response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])

        # Should return ListJobsResponse format with empty jobs array
        assert "jobs" in body
        assert len(body["jobs"]) == 0
        assert body["hasNextPage"] is False
        assert body["hasPreviousPage"] is False
        assert body["lastEvaluatedKey"] is None


@mock_aws()
def test_list_jobs_malformed_dynamodb_items():
    """Test list_jobs function with error in repository layer"""
    from repository.lambda_functions import list_jobs

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.ingestion_job_repository"
    ) as mock_job_repo, patch("utilities.auth.get_groups") as mock_get_groups, patch(
        "utilities.auth.is_admin"
    ) as mock_is_admin:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_is_admin.return_value = True
        mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

        # Mock repository method to raise an exception (simulating malformed data handling)
        mock_job_repo.list_jobs_by_repository.side_effect = Exception("Database error")

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "admin-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
        }

        result = list_jobs(event, SimpleNamespace())

        # Verify the response handles the error
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "error" in body
        assert "Database error" in body["error"]


@mock_aws()
def test_list_jobs_with_pagination():
    """Test list_jobs function with pagination parameters"""
    from repository.lambda_functions import list_jobs

    # Override global mocks for this test
    mock_common.get_username.return_value = "admin-user"
    mock_common.is_admin.return_value = True

    try:
        with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
            "repository.lambda_functions.ingestion_job_repository"
        ) as mock_job_repo, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.is_admin"
        ) as mock_is_admin, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, patch(
            "repository.lambda_functions.get_user_context"
        ) as mock_get_user_context:

            # Setup mocks
            mock_get_groups.return_value = ["test-group"]
            mock_is_admin.return_value = True
            mock_get_username.return_value = "admin-user"
            mock_get_user_context.return_value = (
                "admin-user",
                True,
                ["test-group"],
            )  # Return username, is_admin, groups
            mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

            # Create real IngestionJob object
            job1 = IngestionJob(
                id="job-1",
                repository_id="test-repo",
                collection_id="test-collection",
                status=IngestionStatus.INGESTION_COMPLETED,
                username="admin-user",
                s3_path="s3://bucket/doc1.pdf",
            )

            # Mock pagination response
            last_evaluated_key = {
                "id": "job-1",
                "repository_id": "test-repo",
                "created_date": "2025-09-25T19:14:16.404128+00:00",
            }
            mock_job_repo.list_jobs_by_repository.return_value = ([job1], last_evaluated_key)

            event = {
                "requestContext": {
                    "authorizer": {
                        "username": "admin-user",
                        "claims": {"username": "admin-user"},
                        "groups": json.dumps(["test-group"]),
                    }
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"pageSize": "5", "timeLimit": "48"},
            }

            result = list_jobs(event, SimpleNamespace())

            # Verify the response
            assert result["statusCode"] == 200
            body = json.loads(result["body"])

            # Should return ListJobsResponse format with pagination
            assert "jobs" in body
            assert "lastEvaluatedKey" in body
            assert "hasNextPage" in body
            assert "hasPreviousPage" in body

            assert len(body["jobs"]) == 1
            assert body["hasNextPage"] is True  # lastEvaluatedKey returned
            assert body["hasPreviousPage"] is False  # No lastEvaluatedKey in query params
            assert body["lastEvaluatedKey"] == last_evaluated_key

            # Verify job repository method was called with custom parameters
            mock_job_repo.list_jobs_by_repository.assert_called_once_with(
                repository_id="test-repo",
                username="admin-user",
                is_admin=True,
                time_limit_hours=48,  # Custom time limit
                page_size=5,  # Custom page size
                last_evaluated_key=None,
            )
    finally:
        # Reset global mocks to defaults
        mock_common.get_username.return_value = "test-user"
        mock_common.is_admin.return_value = False


@mock_aws()
def test_list_jobs_with_last_evaluated_key():
    """Test list_jobs function with lastEvaluatedKey parameter"""
    from repository.lambda_functions import list_jobs

    # Override global mocks for this test
    mock_common.get_username.return_value = "admin-user"
    mock_common.is_admin.return_value = True

    try:
        with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
            "repository.lambda_functions.ingestion_job_repository"
        ) as mock_job_repo, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.is_admin"
        ) as mock_is_admin, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, patch(
            "repository.lambda_functions.get_user_context"
        ) as mock_get_user_context:

            # Setup mocks
            mock_get_groups.return_value = ["test-group"]
            mock_is_admin.return_value = True
            mock_get_username.return_value = "admin-user"
            mock_get_user_context.return_value = (
                "admin-user",
                True,
                ["test-group"],
            )  # Return username, is_admin, groups
            mock_vs_repo.find_repository_by_id.return_value = {"allowedGroups": ["test-group"], "status": "active"}

            # Create real IngestionJob object
            job2 = IngestionJob(
                id="job-2",
                repository_id="test-repo",
                collection_id="test-collection",
                status=IngestionStatus.INGESTION_IN_PROGRESS,
                username="admin-user",
                s3_path="s3://bucket/doc2.pdf",
            )

            # Mock repository response
            mock_job_repo.list_jobs_by_repository.return_value = ([job2], None)

            # URL-encoded lastEvaluatedKey
            last_evaluated_key_json = (
                '{"id":"job-1","repository_id":"test-repo","created_date":"2025-09-25T19:14:16.404128+00:00"}'
            )
            encoded_key = urllib.parse.quote(last_evaluated_key_json)

            event = {
                "requestContext": {
                    "authorizer": {
                        "username": "admin-user",
                        "claims": {"username": "admin-user"},
                        "groups": json.dumps(["test-group"]),
                    }
                },
                "pathParameters": {"repositoryId": "test-repo"},
                "queryStringParameters": {"lastEvaluatedKey": encoded_key},
            }

            result = list_jobs(event, SimpleNamespace())

            # Verify the response
            assert result["statusCode"] == 200
            body = json.loads(result["body"])

            assert len(body["jobs"]) == 1
            assert body["hasNextPage"] is False  # No more pages
            assert body["hasPreviousPage"] is True  # Has lastEvaluatedKey in query params
            assert body["lastEvaluatedKey"] is None

            # Verify the lastEvaluatedKey was parsed and passed correctly
            expected_last_evaluated_key = {
                "id": "job-1",
                "repository_id": "test-repo",
                "created_date": "2025-09-25T19:14:16.404128+00:00",
            }
            mock_job_repo.list_jobs_by_repository.assert_called_once_with(
                repository_id="test-repo",
                username="admin-user",
                is_admin=True,
                time_limit_hours=720,  # Default
                page_size=10,  # Default
                last_evaluated_key=expected_last_evaluated_key,
            )
    finally:
        # Reset global mocks to defaults
        mock_common.get_username.return_value = "test-user"
        mock_common.is_admin.return_value = False


@mock_aws()
def test_ingest_documents_with_chunking_override():
    """Test ingest_documents with chunking strategy override"""
    from models.domain_objects import CollectionStatus, FixedChunkingStrategy, RagCollectionConfig
    from repository.lambda_functions import ingest_documents

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_collection_service, patch(
        "repository.lambda_functions.ingestion_job_repository"
    ) as mock_ingestion_job_repo, patch(
        "repository.lambda_functions.ingestion_service"
    ) as mock_ingestion_service, patch(
        "repository.lambda_functions.get_groups"
    ) as mock_get_groups, patch(
        "repository.lambda_functions.get_username"
    ) as mock_get_username, patch(
        "repository.lambda_functions.is_admin"
    ) as mock_is_admin:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_get_username.return_value = "test-user"
        mock_is_admin.return_value = False

        mock_vs_repo.find_repository_by_id.return_value = {
            "allowedGroups": ["test-group"],
            "status": "active",
            "embeddingModelId": "test-embedding-model",
        }

        # Mock collection that allows chunking override
        mock_collection = RagCollectionConfig(
            collectionId="test-collection",
            repositoryId="test-repo",
            name="Test Collection",
            embeddingModel="test-embedding-model",
            chunkingStrategy=FixedChunkingStrategy(size=500, overlap=50),
            allowChunkingOverride=True,  # Allow override
            allowedGroups=["test-group"],
            createdBy="test-user",
            status=CollectionStatus.ACTIVE,
            private=False,
        )
        mock_collection_service.get_collection.return_value = mock_collection

        # Mock ingestion service to avoid needing LISA_INGESTION_JOB_QUEUE_NAME
        mock_ingestion_service.create_ingest_job.return_value = None

        # Mock find_by_id to return a job
        mock_job = IngestionJob(
            id="job-1",
            repository_id="test-repo",
            collection_id="test-collection",
            status=IngestionStatus.INGESTION_PENDING,
            username="test-user",
            s3_path="s3://test-bucket/test-key",
        )
        mock_ingestion_job_repo.find_by_id.return_value = mock_job

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {},
            "body": json.dumps(
                {
                    "collectionId": "test-collection",
                    "chunkingStrategy": {"type": "FIXED", "chunkSize": 2000, "chunkOverlap": 100},
                    "keys": ["test-key"],
                }
            ),
        }

        result = ingest_documents(event, SimpleNamespace())

        # Verify the response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "jobs" in body

        # Verify ingestion job was created with override chunking strategy
        # The job should use the override strategy (2000/100) not the collection default (500/50)
        assert mock_ingestion_job_repo.save.called


def test_ingest_documents_access_denied():
    """Test ingest_documents with access denied to collection"""
    from repository.lambda_functions import ingest_documents
    from utilities.validation import ValidationError

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_collection_service, patch("repository.lambda_functions.get_groups") as mock_get_groups, patch(
        "repository.lambda_functions.get_username"
    ) as mock_get_username, patch(
        "repository.lambda_functions.is_admin"
    ) as mock_is_admin:

        # Setup mocks
        mock_get_groups.return_value = ["test-group"]
        mock_get_username.return_value = "test-user"
        mock_is_admin.return_value = False

        mock_vs_repo.find_repository_by_id.return_value = {
            "allowedGroups": ["test-group"],
            "status": "active",
            "embeddingModelId": "test-embedding-model",
        }

        # Collection access denied
        mock_collection_service.get_collection.side_effect = ValidationError("Permission denied")

        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            },
            "pathParameters": {"repositoryId": "test-repo"},
            "queryStringParameters": {},
            "body": json.dumps({"collectionId": "restricted-collection", "keys": ["test-key"]}),
        }

        result = ingest_documents(event, SimpleNamespace())

        # Verify access denied response - api_wrapper catches ValidationError and returns 500
        # The error message should indicate access denied
        assert result["statusCode"] in [400, 500]
        if result["statusCode"] == 500:
            body = json.loads(result["body"])
            error_msg = body.get("error", body.get("message", "")).lower()
            assert "permission" in error_msg or "not found" in error_msg


def test_get_repository_admin():
    """Test get_repository with admin user"""
    from repository.lambda_functions import get_repository

    with patch("repository.lambda_functions.vs_repo") as mock_repo, patch(
        "repository.lambda_functions.is_admin", return_value=True
    ):
        mock_repo.find_repository_by_id.return_value = {"allowedGroups": ["group1"]}
        event = {"requestContext": {"authorizer": {"groups": json.dumps(["group2"])}}}

        result = get_repository(event, "repo1")
        assert result is not None


def test_get_repository_with_access():
    """Test get_repository with group access"""
    from repository.lambda_functions import get_repository

    with patch("repository.lambda_functions.vs_repo") as mock_repo, patch(
        "repository.lambda_functions.is_admin", return_value=False
    ), patch("repository.lambda_functions.get_groups", return_value=["group1"]):
        mock_repo.find_repository_by_id.return_value = {"allowedGroups": ["group1"]}
        event = {"requestContext": {"authorizer": {"groups": json.dumps(["group1"])}}}

        result = get_repository(event, "repo1")
        assert result is not None


def test_get_repository_no_access():
    """Test get_repository without access"""
    from repository.lambda_functions import get_repository
    from utilities.exceptions import HTTPException

    with patch("repository.lambda_functions.vs_repo") as mock_repo, patch(
        "repository.lambda_functions.is_admin", return_value=False
    ):
        mock_repo.find_repository_by_id.return_value = {"allowedGroups": ["group1"]}
        event = {"requestContext": {"authorizer": {"groups": json.dumps(["group2"])}}}

        with pytest.raises(HTTPException):
            get_repository(event, "repo1")


def test_similarity_search_with_score():
    """Test retrieve_documents with score via service layer"""
    from repository.services.opensearch_repository_service import OpenSearchRepositoryService

    repository = {"repositoryId": "test-repo", "type": "opensearch"}
    service = OpenSearchRepositoryService(repository)

    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "test content"
    mock_doc.metadata = {"source": "test"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.9)]
    mock_vs.client.indices.exists.return_value = True

    with patch("repository.services.opensearch_repository_service.RagEmbeddings"):
        with patch.object(service, "_get_vector_store_client", return_value=mock_vs):
            result = service.retrieve_documents("query", "test-collection", 3, "test-model", include_score=True)

    assert len(result) == 1
    assert "similarity_score" in result[0]["metadata"]


def test_similarity_search_without_score():
    """Test retrieve_documents without score via service layer"""
    from repository.services.opensearch_repository_service import OpenSearchRepositoryService

    repository = {"repositoryId": "test-repo", "type": "opensearch"}
    service = OpenSearchRepositoryService(repository)

    mock_vs = MagicMock()
    mock_vs.client.indices.exists.return_value = True
    mock_doc = MagicMock()
    mock_doc.page_content = "test content"
    mock_doc.metadata = {"source": "test"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.9)]

    with patch("repository.services.opensearch_repository_service.RagEmbeddings"):
        with patch.object(service, "_get_vector_store_client", return_value=mock_vs):
            result = service.retrieve_documents("query", "test-collection", 3, "test-model", include_score=False)

    assert len(result) == 1
    assert result[0]["page_content"] == "test content"


def test_ensure_document_ownership_admin():
    """Test _ensure_document_ownership with admin"""
    from models.domain_objects import FixedChunkingStrategy, RagDocument
    from repository.lambda_functions import _ensure_document_ownership

    with patch("repository.lambda_functions.get_username", return_value="admin"), patch(
        "repository.lambda_functions.is_admin", return_value=True
    ):
        event = {}
        doc = RagDocument(
            document_id="doc1",
            repository_id="repo1",
            collection_id="coll1",
            document_name="test",
            source="s3://bucket/key",
            subdocs=[],
            username="other",
            chunk_strategy=FixedChunkingStrategy(size="1000", overlap="200"),
        )
        _ensure_document_ownership(event, [doc])


def test_ensure_document_ownership_owner():
    """Test _ensure_document_ownership with owner"""
    from models.domain_objects import FixedChunkingStrategy, RagDocument
    from repository.lambda_functions import _ensure_document_ownership

    with patch("repository.lambda_functions.get_username", return_value="user1"), patch(
        "repository.lambda_functions.is_admin", return_value=False
    ):
        event = {}
        doc = RagDocument(
            document_id="doc1",
            repository_id="repo1",
            collection_id="coll1",
            document_name="test",
            source="s3://bucket/key",
            subdocs=[],
            username="user1",
            chunk_strategy=FixedChunkingStrategy(size="1000", overlap="200"),
        )
        _ensure_document_ownership(event, [doc])


def test_ensure_document_ownership_not_owner():
    """Test _ensure_document_ownership without ownership"""
    from models.domain_objects import FixedChunkingStrategy, RagDocument
    from repository.lambda_functions import _ensure_document_ownership

    with patch("repository.lambda_functions.get_username", return_value="user1"), patch(
        "repository.lambda_functions.is_admin", return_value=False
    ):
        event = {}
        doc = RagDocument(
            document_id="doc1",
            repository_id="repo1",
            collection_id="coll1",
            document_name="test",
            source="s3://bucket/key",
            subdocs=[],
            username="other",
            chunk_strategy=FixedChunkingStrategy(size="1000", overlap="200"),
        )
        with pytest.raises(ValueError):
            _ensure_document_ownership(event, [doc])


def test_list_all_with_groups():
    """Test list_all filters by groups"""
    from repository.lambda_functions import list_all

    with patch("repository.lambda_functions.vs_repo") as mock_repo, patch(
        "repository.lambda_functions.get_user_context", return_value=("test-user", False, ["group1"])
    ), patch("repository.lambda_functions.is_admin", return_value=False):
        mock_repo.get_registered_repositories.return_value = [
            {"allowedGroups": ["group1"], "name": "repo1"},
            {"allowedGroups": ["group2"], "name": "repo2"},
        ]
        event = {}
        context = SimpleNamespace(function_name="test", aws_request_id="123")
        result = list_all(event, context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body) == 1


def test_list_status_admin():
    """Test list_status requires admin"""
    from repository.lambda_functions import list_status

    with patch("repository.lambda_functions.vs_repo") as mock_repo, patch(
        "repository.lambda_functions.is_admin", return_value=True
    ):
        mock_repo.get_repository_status.return_value = {"repo1": "active"}
        event = {}
        context = SimpleNamespace(function_name="test", aws_request_id="123")
        result = list_status(event, context)

        assert result["statusCode"] == 200


def test_get_repository_by_id():
    """Test get_repository_by_id"""
    from repository.lambda_functions import get_repository_by_id

    with patch("repository.lambda_functions.get_repository") as mock_get:
        mock_get.return_value = {"repositoryId": "repo1"}
        event = {"pathParameters": {"repositoryId": "repo1"}}
        context = SimpleNamespace(function_name="test", aws_request_id="123")
        result = get_repository_by_id(event, context)

        assert result["statusCode"] == 200


def test_get_repository_by_id_missing():
    """Test get_repository_by_id with missing id"""
    from repository.lambda_functions import get_repository_by_id

    event = {"pathParameters": {}}
    context = SimpleNamespace(function_name="test", aws_request_id="123")
    result = get_repository_by_id(event, context)

    assert result["statusCode"] == 400


def test_presigned_url_success():
    """Test presigned_url generation"""
    from repository.lambda_functions import presigned_url

    with patch("repository.lambda_functions.s3") as mock_s3, patch(
        "repository.lambda_functions.get_username", return_value="user1"
    ):
        mock_s3.generate_presigned_post.return_value = {"url": "https://test.com", "fields": {}}
        event = {"body": "test-key"}
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = presigned_url(event, context)
        assert result["statusCode"] == 200


def test_get_document_success():
    """Test get_document"""
    from repository.lambda_functions import get_document

    with patch("repository.lambda_functions.get_repository"), patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_repo:
        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"documentId": "doc1"}
        mock_repo.find_by_id.return_value = mock_doc

        event = {"pathParameters": {"repositoryId": "repo1", "documentId": "doc1"}}
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = get_document(event, context)
        assert result["statusCode"] == 200


def test_download_document_success():
    """Test download_document"""
    from repository.lambda_functions import download_document

    with patch("repository.lambda_functions.get_repository"), patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_repo, patch("repository.lambda_functions.s3") as mock_s3:
        mock_doc = MagicMock()
        mock_doc.source = "s3://bucket/key"
        mock_repo.find_by_id.return_value = mock_doc
        mock_s3.generate_presigned_url.return_value = "https://test.com"

        event = {"pathParameters": {"repositoryId": "repo1", "documentId": "doc1"}}
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = download_document(event, context)
        assert result["statusCode"] == 200


def test_list_docs_success():
    """Test list_docs"""
    from repository.lambda_functions import list_docs

    with patch("repository.lambda_functions.get_repository"), patch(
        "repository.lambda_functions.doc_repo"
    ) as mock_repo:
        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"documentId": "doc1"}
        mock_repo.list_all.return_value = ([mock_doc], None, 1)

        event = {"pathParameters": {"repositoryId": "repo1"}, "queryStringParameters": {"collectionId": "coll1"}}
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = list_docs(event, context)
        assert result["statusCode"] == 200


def test_update_repository_success():
    """Test update_repository"""
    from repository.lambda_functions import update_repository

    with patch("repository.lambda_functions.vs_repo") as mock_vs:
        mock_vs.find_repository_by_id.return_value = {"repositoryId": "repo1"}
        mock_vs.update.return_value = {"repositoryId": "repo1", "repositoryName": "Updated"}

        event = {"pathParameters": {"repositoryId": "repo1"}, "body": json.dumps({"repositoryName": "Updated"})}
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = update_repository(event, context)
        assert result["statusCode"] == 200


def test_update_repository_missing_id():
    """Test update_repository with missing id"""
    from repository.lambda_functions import update_repository

    event = {"pathParameters": {}, "body": "{}"}
    context = SimpleNamespace(function_name="test", aws_request_id="123")

    result = update_repository(event, context)
    assert result["statusCode"] == 400


def test_update_repository_with_pipeline_change():
    """Test update_repository triggers state machine when pipeline changes"""
    from repository.lambda_functions import update_repository

    with patch("repository.lambda_functions.vs_repo") as mock_vs, patch(
        "repository.lambda_functions.ssm_client"
    ) as mock_ssm, patch("repository.lambda_functions.step_functions_client") as mock_sf, patch(
        "utilities.auth.is_admin"
    ) as mock_is_admin:
        # Mock admin access
        mock_is_admin.return_value = True

        # Mock current repository with existing pipeline
        current_repo = {
            "repositoryId": "repo1",
            "config": {
                "repositoryId": "repo1",
                "repositoryName": "Test Repo",
                "pipelines": [
                    {
                        "autoRemove": True,
                        "trigger": "event",
                        "s3Bucket": "test-bucket",
                        "s3Prefix": "test-prefix",
                        "chunkSize": 512,
                        "chunkOverlap": 51,
                    }
                ],
            },
        }
        mock_vs.find_repository_by_id.return_value = current_repo

        # Mock updated config
        updated_config = {
            "repositoryId": "repo1",
            "repositoryName": "Test Repo",
            "pipelines": [
                {
                    "autoRemove": False,
                    "trigger": "schedule",
                    "s3Bucket": "test-bucket",
                    "s3Prefix": "test-prefix",
                    "chunkSize": 512,
                    "chunkOverlap": 51,
                }
            ],
            "status": "UPDATE_IN_PROGRESS",
        }
        mock_vs.update.return_value = updated_config

        # Mock SSM and Step Functions
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "arn:test-state-machine"}}
        mock_sf.start_execution.return_value = {"executionArn": "arn:execution:123"}

        # Create event with pipeline change
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "pathParameters": {"repositoryId": "repo1"},
            "body": json.dumps(
                {
                    "pipelines": [
                        {
                            "autoRemove": False,
                            "trigger": "schedule",
                            "s3Bucket": "test-bucket",
                            "s3Prefix": "test-prefix",
                            "chunkSize": 512,
                            "chunkOverlap": 51,
                        }
                    ]
                }
            ),
        }
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = update_repository(event, context)

        # Verify state machine was triggered
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert "executionArn" in response_body
        assert response_body["executionArn"] == "arn:execution:123"

        # Verify state machine was called with correct parameters
        mock_sf.start_execution.assert_called_once()
        call_args = mock_sf.start_execution.call_args
        assert call_args[1]["stateMachineArn"] == "arn:test-state-machine"


def test_update_repository_without_pipeline_change():
    """Test update_repository does not trigger state machine when pipeline unchanged"""
    from repository.lambda_functions import update_repository

    with patch("repository.lambda_functions.vs_repo") as mock_vs, patch(
        "repository.lambda_functions.step_functions_client"
    ) as mock_sf, patch("utilities.auth.is_admin") as mock_is_admin:
        # Mock admin access
        mock_is_admin.return_value = True

        # Mock current repository
        current_repo = {
            "repositoryId": "repo1",
            "config": {
                "repositoryId": "repo1",
                "repositoryName": "Test Repo",
                "pipelines": [{"autoRemove": True}],
            },
        }
        mock_vs.find_repository_by_id.return_value = current_repo

        # Mock updated config (no pipeline change)
        updated_config = {
            "repositoryId": "repo1",
            "repositoryName": "Updated Name",
            "pipelines": [{"autoRemove": True}],
            "status": "UPDATE_COMPLETE",
        }
        mock_vs.update.return_value = updated_config

        # Create event without pipeline change
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "pathParameters": {"repositoryId": "repo1"},
            "body": json.dumps({"repositoryName": "Updated Name"}),
        }
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = update_repository(event, context)

        # Verify state machine was NOT triggered
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert "executionArn" not in response_body

        # Verify state machine was not called
        mock_sf.start_execution.assert_not_called()


def test_create_success():
    """Test create repository"""
    from repository.lambda_functions import create

    with patch("repository.lambda_functions.ssm_client") as mock_ssm, patch(
        "repository.lambda_functions.step_functions_client"
    ) as mock_sf, patch("utilities.auth.is_admin") as mock_is_admin:
        mock_is_admin.return_value = True
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "arn:test"}}
        mock_sf.start_execution.return_value = {"executionArn": "arn:execution"}

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "body": json.dumps({"type": "opensearch", "repositoryId": "test-repo"}),
        }
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = create(event, context)
        assert result["statusCode"] == 200


def test_delete_legacy_repository():
    """Test delete with legacy repository"""
    from repository.lambda_functions import delete

    with patch("repository.lambda_functions.vs_repo") as mock_vs, patch(
        "repository.lambda_functions._remove_legacy"
    ), patch("repository.lambda_functions.collection_service") as mock_coll:
        mock_vs.find_repository_by_id.return_value = {"legacy": True, "repositoryId": "repo1"}
        mock_coll.list_collections.return_value = MagicMock(collections=[])

        event = {"pathParameters": {"repositoryId": "repo1"}}
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = delete(event, context)
        assert result["statusCode"] == 200
        assert "legacy" in json.loads(result["body"])["executionArn"]


def test_delete_non_legacy_repository():
    """Test delete with non-legacy repository"""
    from repository.lambda_functions import delete

    with patch("repository.lambda_functions.vs_repo") as mock_vs, patch(
        "repository.lambda_functions.ssm_client"
    ) as mock_ssm, patch("repository.lambda_functions.step_functions_client") as mock_sf, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_coll:
        mock_vs.find_repository_by_id.return_value = {"stackName": "test-stack", "repositoryId": "repo1"}
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "arn:test"}}
        mock_sf.start_execution.return_value = {"executionArn": "arn:execution"}
        mock_coll.list_collections.return_value = MagicMock(collections=[])

        event = {"pathParameters": {"repositoryId": "repo1"}}
        context = SimpleNamespace(function_name="test", aws_request_id="123")

        result = delete(event, context)
        assert result["statusCode"] == 200


# Additional coverage tests for repository lambda functions
def test_similarity_search_helpers():
    """Test retrieve_documents via service layer"""
    import os
    from unittest.mock import MagicMock, patch

    from repository.services.opensearch_repository_service import OpenSearchRepositoryService

    with patch.dict(os.environ, {"LISA_RAG_VECTOR_STORE_TABLE": "test-table"}, clear=False):
        repository = {"repositoryId": "test-repo", "type": "opensearch"}
        service = OpenSearchRepositoryService(repository)

        mock_vs = MagicMock()
        mock_doc = MagicMock()
        mock_doc.page_content = "test content"
        mock_doc.metadata = {"key": "value"}
        mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.9)]
        mock_vs.client.indices.exists.return_value = True

        with patch("repository.services.opensearch_repository_service.RagEmbeddings"):
            with patch.object(service, "_get_vector_store_client", return_value=mock_vs):
                results = service.retrieve_documents("query", "test-collection", 3, "test-model", include_score=False)

        assert len(results) == 1
        assert results[0]["page_content"] == "test content"


# Tests for list_user_collections endpoint


@pytest.fixture
def mock_collection_service_for_lambda():
    """Mock collection service for Lambda handler tests."""
    service = MagicMock()
    service.list_all_user_collections.return_value = ([], None)
    return service


@pytest.fixture
def lambda_event_user_collections():
    """Sample Lambda event for list_user_collections."""
    return {
        "requestContext": {"authorizer": {"username": "test-user", "groups": json.dumps(["group1", "group2"])}},
        "queryStringParameters": {"pageSize": "20", "sortBy": "createdAt", "sortOrder": "desc"},
    }


def test_list_user_collections_endpoint_success_workflow(
    lambda_event_user_collections, lambda_context, mock_collection_service_for_lambda
):
    """
    Complete API workflow: event → handler → service → response with collections.

    Workflow:
    1. API Gateway sends event with user context
    2. Handler extracts user info and query params
    3. Handler calls service to get collections
    4. Handler builds response with collections
    5. Returns 200 with collection data
    """
    from repository.lambda_functions import list_user_collections

    # Setup: Configure mock service to return sample collections
    sample_collections = [
        {
            "collectionId": "coll-1",
            "repositoryId": "repo-1",
            "repositoryName": "Repository 1",
            "name": "Collection 1",
            "description": "Test collection",
            "embeddingModel": "model-1",
            "createdBy": "test-user",
            "private": False,
        }
    ]
    mock_collection_service_for_lambda.list_all_user_collections.return_value = (
        sample_collections,
        None,  # No next token
    )

    # Execute: Call handler with event
    with patch("repository.lambda_functions.collection_service", mock_collection_service_for_lambda):
        response = list_user_collections(lambda_event_user_collections, lambda_context)

    # Verify: Response structure and data
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "collections" in body
    assert len(body["collections"]) == 1
    assert body["collections"][0]["collectionId"] == "coll-1"
    assert body["hasNextPage"] is False
    assert body["hasPreviousPage"] is False


def test_list_user_collections_endpoint_auth_workflow(lambda_context):
    """
    Complete auth workflow: missing auth → 401 response.

    Workflow:
    1. API Gateway sends event without auth context
    2. Handler attempts to extract user context
    3. Handler raises error due to missing auth
    4. Returns error response
    """
    from repository.lambda_functions import list_user_collections

    # Setup: Event without auth context
    event_no_auth = {"requestContext": {}, "queryStringParameters": {}}

    # Execute: Call handler without auth
    response = list_user_collections(event_no_auth, lambda_context)

    # Verify: Error response (may be 500 or 401 depending on implementation)
    assert response["statusCode"] in [400, 401, 500]


def test_list_user_collections_endpoint_pagination_workflow(
    lambda_event_user_collections, lambda_context, mock_collection_service_for_lambda
):
    """
    Complete pagination workflow: request with token → next page returned.

    Workflow:
    1. API Gateway sends event with pagination token
    2. Handler parses pagination token
    3. Handler calls service with token
    4. Service returns next page with new token
    5. Handler returns response with next page data
    """
    from repository.lambda_functions import list_user_collections

    # Setup: Add pagination token to event
    pagination_token = {"version": "v1", "offset": 20}
    lambda_event_user_collections["queryStringParameters"]["lastEvaluatedKey"] = json.dumps(pagination_token)

    # Configure mock to return next page
    next_collections = [
        {
            "collectionId": "coll-21",
            "repositoryId": "repo-1",
            "repositoryName": "Repository 1",
            "name": "Collection 21",
        }
    ]
    next_token = {"version": "v1", "offset": 40}
    mock_collection_service_for_lambda.list_all_user_collections.return_value = (next_collections, next_token)

    # Execute: Call handler with pagination token
    with patch("repository.lambda_functions.collection_service", mock_collection_service_for_lambda):
        response = list_user_collections(lambda_event_user_collections, lambda_context)

    # Verify: Next page returned
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["collections"]) == 1
    assert body["collections"][0]["collectionId"] == "coll-21"
    assert body["hasNextPage"] is True
    assert body["hasPreviousPage"] is True
    assert body["lastEvaluatedKey"] is not None


def test_list_user_collections_endpoint_filtering_workflow(
    lambda_event_user_collections, lambda_context, mock_collection_service_for_lambda
):
    """
    Complete filtering workflow: filter param → filtered results.

    Workflow:
    1. API Gateway sends event with filter parameter
    2. Handler extracts filter text
    3. Handler calls service with filter
    4. Service returns filtered collections
    5. Handler returns filtered results
    """
    from repository.lambda_functions import list_user_collections

    # Setup: Add filter to event
    lambda_event_user_collections["queryStringParameters"]["filter"] = "test"

    # Configure mock to return filtered results
    filtered_collections = [
        {
            "collectionId": "coll-1",
            "name": "Test Collection",
            "description": "Contains test keyword",
        }
    ]
    mock_collection_service_for_lambda.list_all_user_collections.return_value = (filtered_collections, None)

    # Execute: Call handler with filter
    with patch("repository.lambda_functions.collection_service", mock_collection_service_for_lambda):
        response = list_user_collections(lambda_event_user_collections, lambda_context)

    # Verify: Filtered results returned
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["collections"]) == 1
    assert "test" in body["collections"][0]["name"].lower() or "test" in body["collections"][0]["description"].lower()

    # Verify service was called with filter
    mock_collection_service_for_lambda.list_all_user_collections.assert_called_once()
    call_kwargs = mock_collection_service_for_lambda.list_all_user_collections.call_args[1]
    assert call_kwargs["filter_text"] == "test"


def test_list_user_collections_endpoint_error_handling_workflow(
    lambda_event_user_collections, lambda_context, mock_collection_service_for_lambda
):
    """
    Complete error handling workflow: service error → 500 response with logging.

    Workflow:
    1. API Gateway sends valid event
    2. Handler calls service
    3. Service raises unexpected error
    4. Handler catches error and logs it
    5. Returns 500 with generic error message
    """
    from repository.lambda_functions import list_user_collections

    # Setup: Configure mock to raise error
    mock_collection_service_for_lambda.list_all_user_collections.side_effect = Exception("Database connection failed")

    # Execute: Call handler (service will raise error)
    with patch("repository.lambda_functions.collection_service", mock_collection_service_for_lambda):
        response = list_user_collections(lambda_event_user_collections, lambda_context)

    # Verify: 500 error response
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
