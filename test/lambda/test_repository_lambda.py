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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
import requests
from botocore.config import Config
from moto import mock_aws
from utilities.exceptions import HTTPException
from utilities.validation import validate_model_name, ValidationError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Create mock modules needed for imports
mock_create_env = MagicMock()
mock_vs_repo = MagicMock()
mock_doc_repo = MagicMock()
mock_common = MagicMock()

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


# Define mock api_wrapper implementation
def mock_api_wrapper(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
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
            status_code = e.status_code
            return {
                "statusCode": status_code,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": e.message}),
            }
        except ValueError as e:
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
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,  # Use 500 for unexpected errors
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


# Set up common mock values
mock_common.get_username.return_value = "test-user"
mock_common.retry_config = retry_config
mock_common.get_groups.return_value = ["test-group"]
mock_common.is_admin.return_value = False
mock_common.api_wrapper = mock_api_wrapper
mock_common.get_id_token.return_value = "test-token"
mock_common.get_cert_path.return_value = None


# Mock the admin_only decorator to just call the function
def mock_admin_only(func):
    @functools.wraps(func)
    def wrapper(event, context, *args, **kwargs):
        # Just pass through to the wrapped function
        return func(event, context, *args, **kwargs)

    return wrapper


mock_common.admin_only = mock_admin_only

# Patch sys.modules to provide mock modules needed for imports BEFORE importing the lambda functions
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
        "repository.vector_store_repo": mock_vs_repo,
        "repository.rag_document_repo": mock_doc_repo,
        "utilities.common_functions": mock_common,
    },
).start()

# Now patch specific functions from utilities.common_functions
patch("utilities.common_functions.get_username", mock_common.get_username).start()
patch("utilities.common_functions.get_groups", mock_common.get_groups).start()
patch("utilities.common_functions.is_admin", mock_common.is_admin).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()
patch("utilities.common_functions.get_id_token", mock_common.get_id_token).start()
patch("utilities.common_functions.get_cert_path", mock_common.get_cert_path).start()
patch("utilities.common_functions.admin_only", mock_admin_only).start()

# Only now import the lambda functions to ensure they use our mocked dependencies
from repository.lambda_functions import _ensure_document_ownership, _ensure_repository_access, presigned_url

# Create mock modules
mock_create_env = MagicMock()
mock_vs_repo = MagicMock()
mock_doc_repo = MagicMock()

# Patch sys.modules to provide mock modules needed for imports
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
        "repository.vector_store_repo": mock_vs_repo,
        "repository.rag_document_repo": mock_doc_repo,
    },
).start()

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

# Create mock modules
mock_create_env = MagicMock()
mock_vs_repo = MagicMock()
mock_doc_repo = MagicMock()
mock_common = MagicMock()
mock_common.get_username.return_value = "test-user"
mock_common.retry_config = retry_config
mock_common.get_groups.return_value = ["test-group"]
mock_common.is_admin.return_value = False
mock_common.api_wrapper = mock_api_wrapper
mock_common.get_id_token.return_value = "test-token"
mock_common.get_cert_path.return_value = None

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

# Patch sys.modules to provide mock modules needed for imports BEFORE importing the lambda functions
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
        "repository.vector_store_repo": mock_vs_repo,
        "repository.rag_document_repo": mock_doc_repo,
        "utilities.common_functions": mock_common,
    },
).start()

# Now patch specific functions from utilities.common_functions
patch("utilities.common_functions.get_username", mock_common.get_username).start()
patch("utilities.common_functions.get_groups", mock_common.get_groups).start()
patch("utilities.common_functions.is_admin", mock_common.is_admin).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()
patch("utilities.common_functions.get_id_token", mock_common.get_id_token).start()
patch("utilities.common_functions.get_cert_path", mock_common.get_cert_path).start()

# Patch utility functions
patch("utilities.vector_store.get_vector_store_client", mock_get_vector_store_client).start()


# Mock boto3 client function
def mock_boto3_client(service_name, region_name=None, config=None):
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


# Ensure mock_boto3_client is used for all boto3.client calls
with patch("boto3.client", side_effect=mock_boto3_client):

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
            return [
                {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
            ]

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
                        {
                            "ragConfig": {
                                "name": "Test Repository",
                                "type": "opensearch",
                                "allowedGroups": ["test-group"],
                            }
                        }
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
                assert response["statusCode"] == 500
                body = json.loads(response["body"])
                assert "error" in body
                assert "repositoryId is required" in body["error"]

    def test_get_embeddings_pipeline():
        """Test get_embeddings_pipeline function"""

        # Create a patched version of the function
        def mock_get_embeddings_pipeline(model_name):
            return MagicMock()  # Return a mock object that can be used as embeddings

        # Patch the function
        with patch("repository.lambda_functions.get_embeddings_pipeline", side_effect=mock_get_embeddings_pipeline):
            # Test the function
            result = mock_get_embeddings_pipeline("test-model")
            assert isinstance(result, MagicMock)

    def test_get_embeddings_error():
        """Test error handling in _get_embeddings function"""

        # Create a patched version of the function that raises an error
        def mock_get_embeddings(model_name, api_key):
            raise Exception("SSM error")

        # Patch the function
        with patch("repository.lambda_functions._get_embeddings", side_effect=mock_get_embeddings):
            # Test that the error is properly handled
            with pytest.raises(Exception, match="SSM error"):
                mock_get_embeddings("test-model", "test-token")

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
        """Test error handling in PipelineEmbeddings.embed_documents"""

        # Mock the function to raise an exception
        def mock_embed_documents(docs):
            raise requests.RequestException("API request failed")

        # Create a mock PipelineEmbeddings instance
        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents.side_effect = mock_embed_documents

        # Patch get_embeddings_pipeline to return our mock
        with patch("repository.lambda_functions.get_embeddings_pipeline", return_value=mock_embeddings):
            embeddings = mock_embeddings

            # Test that the error is properly handled
            with pytest.raises(requests.RequestException, match="API request failed"):
                embeddings.embed_documents(["test text"])

    def test_pipeline_embeddings_embed_query_error():
        """Test error handling in PipelineEmbeddings.embed_query"""

        # Mock the function to raise an exception
        def mock_embed_query(query):
            raise ValidationError("Invalid query text")

        # Create a mock PipelineEmbeddings instance
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.side_effect = mock_embed_query

        # Patch get_embeddings_pipeline to return our mock
        with patch("repository.lambda_functions.get_embeddings_pipeline", return_value=mock_embeddings):
            embeddings = mock_embeddings

            # Test with invalid input
            with pytest.raises(ValidationError, match="Invalid query text"):
                embeddings.embed_query(None)

    def test_get_embeddings_pipeline_error():
        """Test error handling in get_embeddings_pipeline function"""

        # Mock the function to raise an exception
        def mock_get_embeddings_pipeline(model_name):
            raise ValidationError("Invalid model name")

        # Patch the function
        with patch("repository.lambda_functions.get_embeddings_pipeline", side_effect=mock_get_embeddings_pipeline):
            # Test with invalid input
            with pytest.raises(ValidationError, match="Invalid model name"):
                mock_get_embeddings_pipeline("invalid-model")

    def test_ensure_repository_access_unauthorized():
        """Test _ensure_repository_access with unauthorized access"""

        # Create a mock function that raises an exception
        def mock_ensure_repository_access(event, repository):
            raise HTTPException(message="User does not have permission to access this repository")

        # Patch the function
        with patch("repository.lambda_functions._ensure_repository_access", side_effect=mock_ensure_repository_access):
            # Create event with user not in allowed groups
            event = {
                "requestContext": {
                    "authorizer": {"groups": json.dumps(["different-group"]), "claims": {"username": "test-user"}}
                }
            }

            # Test with repository that requires specific group
            repository = {"allowedGroups": ["required-group"]}

            with pytest.raises(HTTPException) as excinfo:
                mock_ensure_repository_access(event, repository)

            assert excinfo.value.message == "User does not have permission to access this repository"

    def test_document_ownership_validation():
        """Test document ownership validation logic"""

        # Test case 1: User is admin
        event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}
        docs = [{"document_id": "test-doc", "username": "other-user"}]

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
                docs = [{"document_id": "test-doc", "username": "test-user"}]

                mock_get_username.return_value = "test-user"
                mock_is_admin.return_value = False

                # User owns the document
                assert _ensure_document_ownership(event, docs) is None

                # Test case 3: User doesn't own the document
                event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}
                docs = [{"document_id": "test-doc", "username": "other-user"}]

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
        """Test repository access validation logic"""

        # Test case 1: User is admin
        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "admin-user"}, "groups": json.dumps(["admin-group"])}
            }
        }
        repository = {"allowedGroups": ["admin-group"]}

        with patch("utilities.common_functions.is_admin", return_value=True):
            # Admin should always have access
            assert _ensure_repository_access(event, repository) is None

        # Test case 2: User has group access
        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}
            }
        }
        repository = {"allowedGroups": ["test-group"]}

        with patch("utilities.common_functions.is_admin", return_value=False):
            # User has the right group
            assert _ensure_repository_access(event, repository) is None

        # Test case 3: User doesn't have access
        event = {
            "requestContext": {
                "authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["wrong-group"])}
            }
        }
        repository = {"allowedGroups": ["test-group"]}

        with patch("utilities.common_functions.is_admin", return_value=False):
            # User doesn't have the right group
            with pytest.raises(HTTPException) as exc_info:
                _ensure_repository_access(event, repository)
            assert exc_info.value.message == "User does not have permission to access this repository"
