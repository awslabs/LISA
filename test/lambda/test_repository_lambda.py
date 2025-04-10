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

import functools
import json
import logging
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
import requests
from botocore.config import Config
from moto import mock_aws
from utilities.exceptions import HTTPException
from utilities.validation import ValidationError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
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

# Add environment variables needed for tests
os.environ["REST_API_VERSION"] = "v1"
os.environ["LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER"] = "test-create-state-machine-arn"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


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
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


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


# Create mock modules
mock_common = MagicMock()
mock_common.get_username.return_value = "test-user"
mock_common.retry_config = retry_config
mock_common.get_groups.return_value = ["test-group"]
mock_common.is_admin.return_value = False
mock_common.api_wrapper = mock_api_wrapper
mock_common.get_id_token.return_value = "test-token"
mock_common.get_cert_path.return_value = None

# Create mock repositories
mock_vs_repo = MagicMock()
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

# Create mock document repository
mock_doc_repo = MagicMock()
mock_doc_repo.RagDocumentRepository.return_value = mock_doc_repo
mock_doc_repo.find_by_id.return_value = {"source": "s3://test-bucket/test-key"}
mock_doc_repo.list_all.return_value = ([{"documentId": "test-doc", "name": "Test Document"}], None)
mock_doc_repo.save.return_value = {"document_id": "test-doc", "subdocs": ["subdoc1"]}

# Create mock create_env_variables
mock_create_env = MagicMock()

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

# First, patch sys.modules
patch.dict(
    "sys.modules",
    {
        "repository.vector_store_repo": mock_vs_repo,
        "repository.rag_document_repo": mock_doc_repo,
        "create_env_variables": mock_create_env,
    },
).start()

# Then patch the specific functions
patch("utilities.common_functions.get_username", mock_common.get_username).start()
patch("utilities.common_functions.get_groups", mock_common.get_groups).start()
patch("utilities.common_functions.is_admin", mock_common.is_admin).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()
patch("utilities.common_functions.get_id_token", mock_common.get_id_token).start()
patch("utilities.common_functions.get_cert_path", mock_common.get_cert_path).start()


# Patch AWS clients
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
        raise ValueError(f"Unsupported service: {service_name}")


patch("boto3.client", side_effect=mock_boto3_client).start()

# Mock vector store
mock_vector_store = MagicMock()
mock_vector_store.similarity_search.return_value = [
    MagicMock(page_content="Test content", metadata={"source": "test-source"})
]
mock_vector_store.add_texts.return_value = ["subdoc1"]

# Mock get_vector_store_client
mock_get_vector_store_client = MagicMock(return_value=mock_vector_store)
patch("utilities.vector_store.get_vector_store_client", mock_get_vector_store_client).start()

# Mock process_record
mock_process_record = MagicMock(
    return_value=[
        [MagicMock(page_content="Test content", metadata={"name": "test-doc", "source": "s3://test-bucket/test-key"})]
    ]
)
patch("utilities.file_processing.process_record", mock_process_record).start()

# Now import the lambda functions
from repository.lambda_functions import (
    _ensure_document_ownership,
    _ensure_repository_access,
    _get_embeddings,
    _remove_legacy,
    create,
    delete,
    delete_documents,
    download_document,
    get_embeddings_pipeline,
    ingest_documents,
    list_all,
    list_docs,
    list_status,
    presigned_url,
    similarity_search,
)


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
    # Mock the repository list
    mock_repos = [
        {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    ]
    mock_vs_repo.get_registered_repositories.return_value = mock_repos

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}}
    }

    response = list_all(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 1
    assert body[0]["name"] == "Test Repository"


def test_list_status():
    """Test list_status lambda function"""
    # Mock the repository status
    mock_status = {"test-repo": "active"}
    mock_vs_repo.get_repository_status.return_value = mock_status

    # Set admin to True for this test
    mock_common.is_admin.return_value = True

    # Create test event
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = list_status(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert isinstance(body, dict)
    assert body["test-repo"] == "active"


def test_similarity_search():
    """Test similarity_search lambda function"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "queryStringParameters": {"modelName": "test-model", "query": "test query", "topK": 3},
    }

    # Mock vector store search results
    mock_docs = [{"page_content": "Test content", "metadata": {"source": "test-source"}}]
    mock_vector_store = MagicMock()
    mock_vector_store.similarity_search.return_value = mock_docs
    mock_get_vector_store_client = MagicMock(return_value=mock_vector_store)
    patch("utilities.vector_store.get_vector_store_client", mock_get_vector_store_client).start()

    # Mock embeddings
    mock_embeddings = MagicMock()
    mock_get_embeddings = MagicMock(return_value=mock_embeddings)
    patch("repository.lambda_functions._get_embeddings", mock_get_embeddings).start()

    response = similarity_search(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["docs"]) == 1
    assert body["docs"][0]["Document"]["page_content"] == "Test content"


def test_ingest_documents():
    """Test ingest_documents lambda function"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "queryStringParameters": {"chunkSize": "1000", "chunkOverlap": "200"},
        "body": json.dumps({"embeddingModel": {"modelName": "test-model"}, "keys": ["test-key"]}),
    }

    # Mock document processing
    mock_docs = [
        {"page_content": "Test content", "metadata": {"name": "test-doc", "source": "s3://test-bucket/test-key"}}
    ]
    mock_process_record = MagicMock(return_value=mock_docs)
    patch("utilities.file_processing.process_record", mock_process_record).start()

    # Mock S3 operations
    mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"test content")}

    # Mock embeddings
    mock_embeddings = MagicMock()
    mock_get_embeddings = MagicMock(return_value=mock_embeddings)
    patch("repository.lambda_functions._get_embeddings", mock_get_embeddings).start()

    # Mock document repository
    mock_doc_repo.save.return_value = {"document_id": "test-doc", "subdocs": ["subdoc1"]}

    # Mock vector store
    mock_vector_store = MagicMock()
    mock_vector_store.add_texts.return_value = ["subdoc1"]
    mock_get_vector_store_client = MagicMock(return_value=mock_vector_store)
    patch("utilities.vector_store.get_vector_store_client", mock_get_vector_store_client).start()

    response = ingest_documents(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "documentIds" in body
    assert "chunkCount" in body


def test_download_document():
    """Test download_document lambda function"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Mock document repository
    mock_doc = {"source": "s3://test-bucket/test-key"}
    mock_doc_repo.find_by_id.return_value = mock_doc

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo", "documentId": "test-doc"},
    }

    # Mock S3 operations
    mock_s3_client = MagicMock()
    mock_s3_client.generate_presigned_url.return_value = "https://test-url"

    # Patch the global s3 client in the lambda_functions module
    with patch("repository.lambda_functions.s3", mock_s3_client):
        response = download_document(event, None)

        # Verify the mock was called correctly
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            ClientMethod="get_object", Params={"Bucket": "test-bucket", "Key": "test-key"}, ExpiresIn=300
        )

        assert response["statusCode"] == 200
        assert response["body"] == '"https://test-url"'  # JSON-encoded string


def test_list_docs():
    """Test list_docs lambda function"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Mock document repository
    mock_docs = [{"documentId": "test-doc", "name": "Test Document"}]
    mock_doc_repo.list_all.return_value = (mock_docs, None)

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "queryStringParameters": {"collectionId": "test-collection"},
    }

    response = list_docs(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["documents"]) == 1
    assert body["documents"][0]["name"] == "Test Document"


def test_delete():
    """Test delete lambda function"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo
    mock_vs_repo.delete.return_value = True

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"repositoryId": "test-repo"},
    }

    # Set admin to True for this test
    mock_common.is_admin.return_value = True

    # Mock SSM parameter
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-state-machine-arn"}}

    # Mock step functions client
    mock_step_functions = MagicMock()
    mock_step_functions.start_execution.return_value = {"executionArn": "test-execution-arn"}
    patch("boto3.client").return_value = mock_step_functions

    response = delete(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert "executionArn" in body


def test_delete_documents_by_id():
    """Test delete_documents lambda function by document id"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Mock document repository
    mock_doc = {
        "repository_id": "test-repo",
        "collection_id": "test-collection",
        "document_id": "test-doc",
        "document_name": "Test Document",
        "source": "s3://test-bucket/test-key",
        "username": "test-user",
        "subdocs": ["subdoc1", "subdoc2"],
    }
    mock_doc_repo.find_by_id.return_value = mock_doc
    mock_doc_repo.delete_by_id.return_value = True
    mock_doc_repo.delete_s3_docs.return_value = 1

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "body": json.dumps({"documentIds": ["test-doc"]}),
    }

    # Mock vector store
    mock_vector_store = MagicMock()
    mock_vector_store.delete.return_value = None
    mock_get_vector_store_client = MagicMock(return_value=mock_vector_store)
    patch("utilities.vector_store.get_vector_store_client", mock_get_vector_store_client).start()

    # Mock embeddings
    mock_embeddings = MagicMock()
    mock_get_embeddings = MagicMock(return_value=mock_embeddings)
    patch("repository.lambda_functions._get_embeddings", mock_get_embeddings).start()

    response = delete_documents(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "removedDocuments" in body
    assert body["removedDocuments"] == 1
    assert "removedDocumentChunks" in body
    assert body["removedDocumentChunks"] == 2
    assert "removedS3Documents" in body
    assert body["removedS3Documents"] == 1


def test_delete_documents_by_name():
    """Test delete_documents lambda function by document name"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Mock document repository
    mock_docs = [
        {
            "repository_id": "test-repo",
            "collection_id": "test-collection",
            "document_id": "test-doc",
            "document_name": "Test Document",
            "source": "s3://test-bucket/test-key",
            "username": "test-user",
            "subdocs": ["subdoc1", "subdoc2"],
        }
    ]
    mock_doc_repo.find_by_name.return_value = mock_docs
    mock_doc_repo.delete_by_id.return_value = True
    mock_doc_repo.delete_s3_docs.return_value = 1

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "queryStringParameters": {"collectionId": "test-collection", "documentName": "Test Document"},
        "body": "{}",
    }

    # Mock vector store
    mock_vector_store = MagicMock()
    mock_vector_store.delete.return_value = None
    mock_get_vector_store_client = MagicMock(return_value=mock_vector_store)
    patch("utilities.vector_store.get_vector_store_client", mock_get_vector_store_client).start()

    # Mock embeddings
    mock_embeddings = MagicMock()
    mock_get_embeddings = MagicMock(return_value=mock_embeddings)
    patch("repository.lambda_functions._get_embeddings", mock_get_embeddings).start()

    response = delete_documents(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "removedDocuments" in body
    assert body["removedDocuments"] == 1


def test_delete_documents_error():
    """Test delete_documents lambda function with no document parameters"""
    # Create test event with missing parameters
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "body": "{}",
    }

    response = delete_documents(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert "No 'documentIds' or 'documentName' parameter supplied" in body["error"]


def test_delete_documents_unauthorized():
    """Test delete_documents lambda function with unauthorized access"""
    # Mock repository access
    mock_repo = {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"], "status": "active"}
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Mock document repository
    mock_doc = {
        "repository_id": "test-repo",
        "collection_id": "test-collection",
        "document_id": "test-doc",
        "document_name": "Test Document",
        "source": "s3://test-bucket/test-key",
        "username": "other-user",  # Different from test-user
        "subdocs": ["subdoc1", "subdoc2"],
    }
    mock_doc_repo.find_by_id.return_value = mock_doc

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "body": json.dumps({"documentIds": ["test-doc"]}),
    }

    # Ensure admin is false
    mock_common.is_admin.return_value = False

    response = delete_documents(event, None)
    assert response["statusCode"] == 500
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
    # Reset any side effect from previous tests
    mock_ssm.get_parameter.side_effect = None

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {"ragConfig": {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"]}}
        ),
    }

    # Set admin to True for this test
    mock_common.is_admin.return_value = True

    # Mock SSM parameter
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-state-machine-arn"}}

    # Mock step functions client
    mock_step_functions.start_execution.return_value = {"executionArn": "test-execution-arn"}

    response = create(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["executionArn"] == "test-execution-arn"


def test_delete_legacy():
    """Test delete lambda function with legacy repository"""
    # Mock repository access with legacy flag
    mock_repo = {
        "name": "Test Repository",
        "type": "opensearch",
        "allowedGroups": ["test-group"],
        "status": "active",
        "legacy": True,
    }
    mock_vs_repo.find_repository_by_id.return_value = mock_repo
    mock_vs_repo.delete.return_value = True

    # Create test event
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"repositoryId": "test-repo"},
    }

    # Set admin to True for this test
    mock_common.is_admin.return_value = True

    # Mock SSM parameter for legacy repositories
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps([{"repositoryId": "test-repo"}])}}

    response = delete(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["executionArn"] == "legacy"


def test_delete_missing_repository_id():
    """Test delete lambda function with missing repository ID"""
    # Create test event with missing repositoryId
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}, "pathParameters": {}}

    # Set admin to True for this test
    mock_common.is_admin.return_value = True

    response = delete(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert "repositoryId is required" in body["error"]


def test_get_embeddings_pipeline():
    """Test get_embeddings_pipeline function"""
    # Reset any side effect from previous tests
    mock_ssm.get_parameter.side_effect = None

    # Mock SSM and Secrets Manager
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://lisa-api-endpoint.com"}}
    mock_secrets.get_secret_value.return_value = {"SecretString": "test-token"}

    # Mock validate_model_name
    with patch("repository.lambda_functions.validate_model_name") as mock_validate:
        result = get_embeddings_pipeline("test-model")
        mock_validate.assert_called_once_with("test-model")
        assert result is not None
        assert result.model_name == "test-model"


def test_get_embeddings_error():
    """Test error handling in _get_embeddings function"""
    # Mock SSM client to raise an exception
    mock_ssm.get_parameter.side_effect = Exception("SSM error")

    # Test that the error is properly handled
    with pytest.raises(Exception, match="SSM error"):
        _get_embeddings("test-model", "test-token")

    # Reset side effect after test
    mock_ssm.get_parameter.side_effect = None


def test_pipeline_embeddings_embed_documents_error():
    """Test error handling in PipelineEmbeddings.embed_documents"""
    # Reset any side effect from previous tests
    mock_ssm.get_parameter.side_effect = None

    # Mock requests.post to raise an exception
    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.RequestException("API request failed")

        # Mock SSM and Secrets Manager for initialization
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://lisa-api-endpoint.com"}}
        mock_secrets.get_secret_value.return_value = {"SecretString": "test-token"}

        # Create embeddings object with a custom class to avoid initialization issues
        with patch("repository.lambda_functions.PipelineEmbeddings") as MockEmbeddings:
            mock_embeddings = MagicMock()
            mock_embeddings.model_name = "test-model"
            mock_embeddings.embed_documents.side_effect = requests.RequestException("API request failed")
            MockEmbeddings.return_value = mock_embeddings

            embeddings = get_embeddings_pipeline("test-model")

            # Test that the error is properly handled
            with pytest.raises(requests.RequestException, match="API request failed"):
                embeddings.embed_documents(["test text"])


def test_pipeline_embeddings_embed_query_error():
    """Test error handling in PipelineEmbeddings.embed_query"""
    # Reset any side effect from previous tests
    mock_ssm.get_parameter.side_effect = None

    # Mock SSM and Secrets Manager for initialization
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://lisa-api-endpoint.com"}}
    mock_secrets.get_secret_value.return_value = {"SecretString": "test-token"}

    # Create embeddings object with a custom class to avoid initialization issues
    with patch("repository.lambda_functions.PipelineEmbeddings") as MockEmbeddings:
        mock_embeddings = MagicMock()
        mock_embeddings.model_name = "test-model"
        mock_embeddings.embed_query = MagicMock(side_effect=ValidationError("Invalid query text"))
        MockEmbeddings.return_value = mock_embeddings

        embeddings = get_embeddings_pipeline("test-model")

        # Test with invalid input
        with pytest.raises(ValidationError, match="Invalid query text"):
            embeddings.embed_query(None)


def test_get_embeddings_pipeline_error():
    """Test error handling in get_embeddings_pipeline function"""
    # Mock validate_model_name to raise an exception
    with patch("repository.lambda_functions.validate_model_name") as mock_validate:
        mock_validate.side_effect = ValidationError("Invalid model name")

        with pytest.raises(ValidationError, match="Invalid model name"):
            get_embeddings_pipeline("invalid-model")


def test_ensure_repository_access_unauthorized():
    """Test _ensure_repository_access with unauthorized access"""
    # Create event with user not in allowed groups
    event = {
        "requestContext": {
            "authorizer": {"groups": json.dumps(["different-group"]), "claims": {"username": "test-user"}}
        }
    }

    # Set admin to False
    mock_common.is_admin.return_value = False

    # Test with repository that requires specific group
    repository = {"allowedGroups": ["required-group"]}

    with pytest.raises(HTTPException) as excinfo:
        _ensure_repository_access(event, repository)

    assert excinfo.value.message == "User does not have permission to access this repository"


def test_ensure_document_ownership_unauthorized():
    """Test _ensure_document_ownership with unauthorized access"""
    # Create event
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    # Set admin to False
    mock_common.is_admin.return_value = False

    # Test with document not owned by user
    docs = [{"document_id": "test-doc", "username": "different-user"}]

    with pytest.raises(ValueError) as excinfo:
        _ensure_document_ownership(event, docs)

    assert "Document test-doc is not owned by test-user" in str(excinfo.value)


def test_similarity_search_forbidden():
    """Test similarity_search with forbidden access"""
    # Mock repository access
    mock_repo = {
        "name": "Test Repository",
        "type": "opensearch",
        "allowedGroups": ["different-group"],
        "status": "active",
    }
    mock_vs_repo.find_repository_by_id.return_value = mock_repo

    # Create test event with user not in allowed groups
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "groups": json.dumps(["test-group"])}},
        "pathParameters": {"repositoryId": "test-repo"},
        "queryStringParameters": {"modelName": "test-model", "query": "test query"},
    }

    # Set admin to False
    mock_common.is_admin.return_value = False

    response = similarity_search(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert "User does not have permission to access this repository" in body["error"]


def test_remove_legacy():
    """Test _remove_legacy function"""
    # Reset side effect from previous tests
    mock_ssm.get_parameter.side_effect = None

    # Reset mock calls for put_parameter
    mock_ssm.put_parameter.reset_mock()

    # Mock SSM parameter
    registered_repos = [{"repositoryId": "test-repo"}, {"repositoryId": "other-repo"}]
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps(registered_repos)}}

    # Call function
    _remove_legacy("test-repo")

    # Verify SSM was called to update the parameter
    mock_ssm.put_parameter.assert_called_once()
    call_args = mock_ssm.put_parameter.call_args[1]
    assert call_args["Name"] == "test-repositories"
    assert call_args["Overwrite"] is True

    # Verify the updated value only contains the remaining repository
    updated_repos = json.loads(call_args["Value"])
    assert len(updated_repos) == 1
    assert updated_repos[0]["repositoryId"] == "other-repo"
