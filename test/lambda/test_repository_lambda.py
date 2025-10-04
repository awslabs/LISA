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

"""
Refactored repository lambda tests using fixture-based mocking instead of global mocks.
This replaces the original test_repository_lambda.py with isolated, maintainable tests.
"""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from conftest import LambdaTestHelper, RepositoryTestHelper
from moto import mock_aws


# Set up test environment variables
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "LISA_RAG_VECTOR_STORE_TABLE": "vector-store-table",
        "RAG_DOCUMENT_TABLE": "rag-document-table",
        "RAG_SUB_DOCUMENT_TABLE": "rag-sub-document-table",
        "BUCKET_NAME": "test-bucket",
        "LISA_API_URL_PS_NAME": "test-api-url",
        "MANAGEMENT_KEY_SECRET_NAME_PS": "test-secret-name",
        "REGISTERED_REPOSITORIES_PS": "test-repositories",
        "LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER": "test-state-machine-arn",
        "REST_API_VERSION": "v1",
        "LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER": "test-create-state-machine-arn",
        "LISA_INGESTION_JOB_TABLE_NAME": "testing-ingestion-table",
    }

    for key, value in env_vars.items():
        os.environ[key] = value

    yield

    # Cleanup
    for key in env_vars.keys():
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def dynamodb_service():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture
def vector_store_table(dynamodb_service):
    """Create a mock DynamoDB table for vector store."""
    table = dynamodb_service.create_table(
        TableName="vector-store-table",
        KeySchema=[{"AttributeName": "repositoryId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "repositoryId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table.wait_until_exists()
    return table


@pytest.fixture
def rag_document_table(dynamodb_service):
    """Create a mock DynamoDB table for RAG documents."""
    table = dynamodb_service.create_table(
        TableName="rag-document-table",
        KeySchema=[{"AttributeName": "documentId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "documentId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table.wait_until_exists()
    return table


@pytest.fixture
def rag_sub_document_table(dynamodb_service):
    """Create a mock DynamoDB table for RAG sub-documents."""
    table = dynamodb_service.create_table(
        TableName="rag-sub-document-table",
        KeySchema=[{"AttributeName": "subDocumentId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "subDocumentId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table.wait_until_exists()
    return table


@pytest.fixture
def mock_vector_store():
    """Mock vector store client."""
    mock_client = MagicMock()
    mock_client.similarity_search.return_value = [
        MagicMock(page_content="Test content", metadata={"source": "test-source"})
    ]
    mock_client.add_texts.return_value = ["subdoc1"]
    return mock_client


@pytest.fixture
def mock_embeddings():
    """Mock embeddings service."""
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents.return_value = [[0.1, 0.2, 0.3]]
    mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
    return mock_embeddings


# Test list_all function
def test_list_all(mock_auth_context, mock_repository_services, lambda_context):
    """Test list_all lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import list_all

    # Create test event
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    # list_all doesn't need repositoryId, so clear pathParameters
    event["pathParameters"] = {}

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]):
        response = list_all(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 1
    assert body[0]["name"] == "Test Repository"


def test_list_status(mock_admin_auth_context, mock_repository_services, lambda_context):
    """Test list_status lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import list_status

    # Create test event
    event = RepositoryTestHelper.create_repository_event("admin-user", ["admin-group"])
    # list_status doesn't need repositoryId, so clear pathParameters
    event["pathParameters"] = {}

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]):
        response = list_status(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert isinstance(body, dict)
    assert body["test-repo"] == "active"


def test_similarity_search(
    mock_auth_context,
    mock_repository_services,
    mock_vector_store,
    mock_embeddings,
    mock_api_wrapper_bypass,
    lambda_context,
):
    """Test similarity_search lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import similarity_search

    # Create test event
    event = RepositoryTestHelper.create_repository_event(
        "test-user",
        ["test-group"],
        path_params={"repositoryId": "test-repo"},
        query_params={"modelName": "test-model", "query": "test query", "topK": "3"},
    )

    # Mock vector store to return similarity search results
    mock_vector_store.similarity_search_with_score.return_value = [
        (MagicMock(page_content="Test content", metadata={"source": "test-source"}), 0.8)
    ]

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.get_vector_store_client", return_value=mock_vector_store
    ), patch("repository.embeddings.RagEmbeddings", return_value=mock_embeddings), patch(
        "utilities.common_functions.get_id_token", return_value="test-token"
    ), patch(
        "repository.embeddings.get_rest_api_container_endpoint", return_value="https://api.test.com"
    ), patch(
        "repository.embeddings.get_cert_path", return_value="/test/cert"
    ), patch(
        "repository.embeddings.get_management_key", return_value="test-key"
    ):

        response = similarity_search(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "docs" in body
    assert len(body["docs"]) >= 1


def test_similarity_search_forbidden(mock_auth_context, mock_repository_services, lambda_context):
    """Test similarity_search with forbidden access - REFACTORED VERSION."""
    from repository.lambda_functions import similarity_search

    # Create test event with user not in allowed groups
    event = RepositoryTestHelper.create_repository_event(
        "test-user",
        ["wrong-group"],
        path_params={"repositoryId": "test-repo"},
        query_params={"modelName": "test-model", "query": "test query"},
    )

    # Mock repository that requires different group
    mock_repository_services["vs_repo"].find_repository_by_id.return_value = {
        "allowedGroups": ["admin-group"],
        "status": "active",
    }

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]):
        response = similarity_search(event, lambda_context)

    # Verify forbidden response - api_wrapper will return 403 directly when HTTPException is raised
    assert response["statusCode"] == 403


def test_ingest_documents(mock_auth_context, mock_repository_services, lambda_context):
    """Test ingest_documents lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import ingest_documents

    # Create test event
    event = RepositoryTestHelper.create_repository_event(
        "test-user",
        ["test-group"],
        path_params={"repositoryId": "test-repo"},
        query_params={"chunkSize": "1000", "chunkOverlap": "200"},
        body={"embeddingModel": {"modelName": "test-model"}, "keys": ["test-key"]},
    )

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.ingestion_service", mock_repository_services["ingestion_service"]
    ), patch("repository.lambda_functions.ingestion_job_repository", mock_repository_services["ingestion_service"]):

        response = ingest_documents(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "ingestionJobIds" in body  # Updated to match actual return from function


def test_download_document(mock_auth_context, mock_repository_services, mock_aws_magicmock_services, lambda_context):
    """Test download_document lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import download_document

    # Create test event
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    event["pathParameters"] = {"repositoryId": "test-repo", "documentId": "test-doc"}

    # Set up mock document with ownership
    mock_doc = MagicMock()
    mock_doc.source = "s3://test-bucket/test-key"
    mock_doc.username = "test-user"
    mock_repository_services["doc_repo"].find_by_id.return_value = mock_doc

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.doc_repo", mock_repository_services["doc_repo"]
    ), patch("repository.lambda_functions.s3", mock_aws_magicmock_services["s3"]):

        response = download_document(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    # Response body is JSON-encoded URL string
    assert response["body"] == '"https://test-presigned-url"'


def test_list_docs(mock_auth_context, mock_repository_services, lambda_context):
    """Test list_docs lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import list_docs

    # Create test event
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    event["pathParameters"] = {"repositoryId": "test-repo"}
    event["queryStringParameters"] = {"collectionId": "test-collection"}

    # Create mock document with model_dump method
    mock_doc = MagicMock()
    mock_doc.model_dump.return_value = {"documentId": "test-doc", "name": "Test Document"}
    mock_repository_services["doc_repo"].list_all.return_value = ([mock_doc], None, 1)

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.doc_repo", mock_repository_services["doc_repo"]
    ):

        response = list_docs(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "documents" in body
    assert len(body["documents"]) == 1
    assert body["documents"][0]["name"] == "Test Document"


def test_list_docs_with_pagination(mock_auth_context, mock_repository_services, lambda_context):
    """Test list_docs with pagination - REFACTORED VERSION."""
    from repository.lambda_functions import list_docs

    # Create test event with pagination parameters
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    event["pathParameters"] = {"repositoryId": "test-repo"}
    event["queryStringParameters"] = {
        "collectionId": "test-collection",
        "lastEvaluatedKeyPk": "current-page",
        "lastEvaluatedKeyDocumentId": "doc1",
        "lastEvaluatedKeyRepositoryId": "test-repo",
        "pageSize": "2",
    }

    # Create mock documents
    mock_doc1 = MagicMock()
    mock_doc1.model_dump.return_value = {"documentId": "doc1", "name": "Document 1"}
    mock_doc2 = MagicMock()
    mock_doc2.model_dump.return_value = {"documentId": "doc2", "name": "Document 2"}

    # Mock list_all to return documents with pagination info
    mock_repository_services["doc_repo"].list_all.return_value = (
        [mock_doc1, mock_doc2],
        {"pk": "next-page", "document_id": "doc2"},
        5,
    )

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.doc_repo", mock_repository_services["doc_repo"]
    ):

        response = list_docs(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["documents"]) == 2
    assert body["totalDocuments"] == 5
    assert body["hasNextPage"] is True
    assert body["hasPreviousPage"] is False
    assert body["lastEvaluated"] == {"pk": "next-page", "document_id": "doc2"}


def test_delete_documents_by_id(
    mock_auth_context, mock_repository_services, mock_vector_store, mock_api_wrapper_bypass, lambda_context
):
    """Test delete_documents by document ID - REFACTORED VERSION."""
    from repository.lambda_functions import delete_documents

    # Create test event
    event = RepositoryTestHelper.create_repository_event(
        "test-user", ["test-group"], path_params={"repositoryId": "test-repo"}, body={"documentIds": ["test-doc"]}
    )

    # Set up mock document with ownership - make it behave like a real RagDocument
    # The _ensure_document_ownership function calls doc.get('document_id') and doc.get('username')
    mock_doc = MagicMock()
    mock_doc.username = "test-user"
    mock_doc.document_id = "test-doc"
    mock_doc.repository_id = "test-repo"
    mock_doc.collection_id = "test-collection"  # String value needed for pydantic validation
    mock_doc.source = "s3://test-bucket/test-key"

    # Set up the get() method to return the correct values
    def mock_get(key, default=None):
        if key == "document_id":
            return "test-doc"
        elif key == "username":
            return "test-user"
        return default

    mock_doc.get = mock_get

    mock_doc.model_dump.return_value = {
        "document_id": "test-doc",
        "username": "test-user",
        "repository_id": "test-repo",
        "collection_id": "test-collection",
        "source": "s3://test-bucket/test-key",
    }
    mock_repository_services["doc_repo"].find_by_id.return_value = mock_doc

    # Mock ingestion job repository
    mock_ingestion_job_repo = MagicMock()
    mock_ingestion_job_repo.find_by_document.return_value = None
    mock_ingestion_job_repo.save.return_value = None

    # Mock ingestion service
    mock_ingestion_service = MagicMock()
    mock_ingestion_service.create_delete_job.return_value = None

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.doc_repo", mock_repository_services["doc_repo"]
    ), patch("repository.lambda_functions.ingestion_job_repository", mock_ingestion_job_repo), patch(
        "repository.lambda_functions.ingestion_service", mock_ingestion_service
    ), patch(
        "repository.lambda_functions.get_username", return_value="test-user"
    ), patch(
        "repository.lambda_functions.is_admin", return_value=False
    ), patch(
        "utilities.vector_store.get_vector_store_client", return_value=mock_vector_store
    ):

        response = delete_documents(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "documentIds" in body
    assert body["documentIds"] == ["test-doc"]


def test_delete_documents_unauthorized(mock_auth_context, mock_repository_services, lambda_context):
    """Test delete_documents with unauthorized access - REFACTORED VERSION."""
    from repository.lambda_functions import delete_documents

    # Create test event
    event = RepositoryTestHelper.create_repository_event(
        "test-user", ["test-group"], path_params={"repositoryId": "test-repo"}, body={"documentIds": ["test-doc"]}
    )

    # Set up mock document owned by different user
    mock_doc = MagicMock()
    mock_doc.username = "other-user"
    mock_doc.document_id = "test-doc"

    # Set up the get() method to return the correct values
    def mock_get(key, default=None):
        if key == "document_id":
            return "test-doc"
        elif key == "username":
            return "other-user"
        return default

    mock_doc.get = mock_get

    mock_repository_services["doc_repo"].find_by_id.return_value = mock_doc

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.doc_repo", mock_repository_services["doc_repo"]
    ), patch("repository.lambda_functions.get_username", return_value="test-user"), patch(
        "repository.lambda_functions.is_admin", return_value=False
    ):

        response = delete_documents(event, lambda_context)

    # Should return error due to ownership mismatch - ValueError returns 400
    assert response["statusCode"] == 400


def test_presigned_url(mock_auth_context, mock_aws_magicmock_services, lambda_context):
    """Test presigned_url lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import presigned_url

    # Create test event
    event = LambdaTestHelper.create_basic_event("test-user")
    event["body"] = "test-key"

    # Configure S3 mock
    mock_aws_magicmock_services["s3"].generate_presigned_post.return_value = {
        "url": "https://test-bucket.s3.amazonaws.com",
        "fields": {"key": "test-key"},
    }

    # Mock dependencies
    with patch("repository.lambda_functions.s3", mock_aws_magicmock_services["s3"]):
        response = presigned_url(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "response" in body
    assert "url" in body["response"]
    assert body["response"]["url"].startswith("https://test-bucket.s3.amazonaws.com")


def test_create(mock_admin_auth_context, mock_aws_magicmock_services, lambda_context):
    """Test create lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import create

    # Create test event
    event = LambdaTestHelper.create_basic_event("admin-user")
    event["body"] = json.dumps(
        {"ragConfig": {"name": "Test Repository", "type": "opensearch", "allowedGroups": ["test-group"]}}
    )

    # Configure mocks
    mock_aws_magicmock_services["ssm"].get_parameter.return_value = {"Parameter": {"Value": "test-arn"}}
    mock_aws_magicmock_services["stepfunctions"].start_execution.return_value = {"executionArn": "test-execution-arn"}

    # Mock dependencies
    with patch("repository.lambda_functions.ssm_client", mock_aws_magicmock_services["ssm"]), patch(
        "repository.lambda_functions.step_functions_client", mock_aws_magicmock_services["stepfunctions"]
    ):

        response = create(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["executionArn"] == "test-execution-arn"


def test_delete(mock_admin_auth_context, mock_repository_services, mock_aws_magicmock_services, lambda_context):
    """Test delete lambda function - REFACTORED VERSION."""
    from repository.lambda_functions import delete

    # Create test event
    event = LambdaTestHelper.create_basic_event("admin-user")
    event["pathParameters"] = {"repositoryId": "test-repo"}

    # Configure mocks
    mock_aws_magicmock_services["ssm"].get_parameter.return_value = {"Parameter": {"Value": "test-arn"}}
    mock_aws_magicmock_services["stepfunctions"].start_execution.return_value = {"executionArn": "test-execution-arn"}

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.ssm_client", mock_aws_magicmock_services["ssm"]
    ), patch("repository.lambda_functions.step_functions_client", mock_aws_magicmock_services["stepfunctions"]):

        response = delete(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["executionArn"] == "test-execution-arn"


def test_delete_legacy(mock_admin_auth_context, mock_repository_services, mock_aws_magicmock_services, lambda_context):
    """Test delete lambda function with legacy repository - REFACTORED VERSION."""
    from repository.lambda_functions import delete

    # Create test event
    event = LambdaTestHelper.create_basic_event("admin-user")
    event["pathParameters"] = {"repositoryId": "legacy-repo"}

    # Configure legacy repository
    mock_repository_services["vs_repo"].find_repository_by_id.return_value = {"legacy": True}

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions._remove_legacy"
    ) as mock_remove_legacy:

        mock_remove_legacy.return_value = None

        response = delete(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["executionArn"] == "legacy"


def test_delete_missing_repository_id(mock_admin_auth_context, lambda_context):
    """Test delete lambda function with missing repository ID - REFACTORED VERSION."""
    from repository.lambda_functions import delete

    # Create test event with missing repositoryId
    event = LambdaTestHelper.create_basic_event("admin-user")
    event["pathParameters"] = {}

    response = delete(event, lambda_context)

    # Should return error response - ValidationError returns 400
    assert response["statusCode"] == 400


def test_bedrock_knowledge_base_similarity_search(
    mock_auth_context, mock_repository_services, mock_aws_services, lambda_context
):
    """Test similarity_search for Bedrock Knowledge Base repositories - REFACTORED VERSION."""
    from repository.lambda_functions import similarity_search

    # Create test event
    event = RepositoryTestHelper.create_repository_event(
        "test-user",
        ["test-group"],
        path_params={"repositoryId": "test-repo"},
        query_params={"modelName": "test-model", "query": "test query", "topK": "2"},
    )

    # Configure Bedrock KB repository
    mock_repository_services["vs_repo"].find_repository_by_id.return_value = {
        "type": "bedrock_knowledge_base",
        "allowedGroups": ["test-group"],
        "bedrockKnowledgeBaseConfig": {"bedrockKnowledgeBaseId": "kb-123"},
        "status": "active",
    }

    # Configure Bedrock client response
    mock_aws_services["bedrock-agent-runtime"].retrieve.return_value = {
        "retrievalResults": [
            {"content": {"text": "KB doc content"}, "location": {"s3Location": {"uri": "s3://bucket/path/doc1.pdf"}}},
            {"content": {"text": "Second content"}, "location": {"s3Location": {"uri": "s3://bucket/path/doc2.txt"}}},
        ]
    }

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.bedrock_client", mock_aws_services["bedrock-agent-runtime"]
    ), patch("utilities.common_functions.get_id_token", return_value="test-token"):

        response = similarity_search(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "docs" in body
    assert len(body["docs"]) == 2
    first_doc = body["docs"][0]["Document"]
    assert first_doc["page_content"] == "KB doc content"
    assert first_doc["metadata"]["source"] == "s3://bucket/path/doc1.pdf"
    assert first_doc["metadata"]["name"] == "doc1.pdf"


# Test helper function validation
def test_ensure_repository_access(mock_auth_context):
    """Test _ensure_repository_access helper function - REFACTORED VERSION."""
    from repository.lambda_functions import _ensure_repository_access
    from utilities.exceptions import HTTPException

    # Test case 1: User has group access
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    repository = {"allowedGroups": ["test-group"]}

    with patch("utilities.auth.is_admin", return_value=False):
        # Should not raise exception
        assert _ensure_repository_access(event, repository) is None

    # Test case 2: User doesn't have access
    event = RepositoryTestHelper.create_repository_event("test-user", ["wrong-group"])
    repository = {"allowedGroups": ["test-group"]}

    with patch("utilities.auth.is_admin", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            _ensure_repository_access(event, repository)
        assert exc_info.value.message == "User does not have permission to access this repository"


def test_ensure_document_ownership(mock_auth_context):
    """Test _ensure_document_ownership helper function - REFACTORED VERSION."""
    from repository.lambda_functions import _ensure_document_ownership

    # Test case 1: User owns the document
    event = LambdaTestHelper.create_basic_event("test-user")
    docs = [{"document_id": "test-doc", "username": "test-user"}]

    with patch("repository.lambda_functions.get_username", return_value="test-user"), patch(
        "repository.lambda_functions.is_admin", return_value=False
    ):

        # Should not raise exception
        assert _ensure_document_ownership(event, docs) is None

    # Test case 2: User doesn't own the document (non-admin)
    event = LambdaTestHelper.create_basic_event("test-user")
    docs = [{"document_id": "test-doc", "username": "other-user"}]

    with patch("repository.lambda_functions.get_username", return_value="test-user"), patch(
        "repository.lambda_functions.is_admin", return_value=False
    ):

        with pytest.raises(ValueError) as exc_info:
            _ensure_document_ownership(event, docs)
        assert "Document test-doc is not owned by test-user" in str(exc_info.value)

    # Test case 3: Admin user can access any document
    event = LambdaTestHelper.create_basic_event("admin-user")
    docs = [{"document_id": "test-doc", "username": "other-user"}]

    with patch("repository.lambda_functions.get_username", return_value="admin-user"), patch(
        "repository.lambda_functions.is_admin", return_value=True
    ):

        # Admin should have access to any document
        assert _ensure_document_ownership(event, docs) is None


# Test embeddings functionality
def test_rag_embeddings(mock_aws_services):
    """Test RagEmbeddings functionality - REFACTORED VERSION."""
    from repository.embeddings import RagEmbeddings

    # Mock the dependencies
    with patch("repository.embeddings.get_rest_api_container_endpoint", return_value="https://api.example.com"), patch(
        "repository.embeddings.get_cert_path", return_value="/path/to/cert"
    ), patch("repository.embeddings.get_management_key", return_value="test-token"), patch(
        "repository.embeddings.requests.post"
    ) as mock_post:

        # Configure successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_post.return_value = mock_response

        # Test initialization
        embeddings = RagEmbeddings("test-model", "test-token")
        assert embeddings.model_name == "test-model"

        # Test embed_documents
        result = embeddings.embed_documents(["test text"])
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

        # Test embed_query
        result = embeddings.embed_query("test query")
        assert result == [0.1, 0.2, 0.3]


def test_rag_embeddings_error_handling():
    """Test RagEmbeddings error handling - REFACTORED VERSION."""
    from repository.embeddings import RagEmbeddings
    from utilities.validation import ValidationError

    with patch("repository.embeddings.get_rest_api_container_endpoint", return_value="https://api.example.com"), patch(
        "repository.embeddings.get_cert_path", return_value="/path/to/cert"
    ), patch("repository.embeddings.get_management_key", return_value="test-token"):

        embeddings = RagEmbeddings("test-model", "test-token")

        # Test embed_documents with empty list
        with pytest.raises(ValidationError, match="No texts provided for embedding"):
            embeddings.embed_documents([])

        # Test embed_query with invalid input
        with pytest.raises(ValidationError, match="Invalid query text"):
            embeddings.embed_query(None)

        with pytest.raises(ValidationError, match="Invalid query text"):
            embeddings.embed_query("")


def test_remove_legacy(mock_aws_magicmock_services):
    """Test _remove_legacy function - REFACTORED VERSION."""
    from repository.lambda_functions import _remove_legacy

    # Mock SSM to return valid JSON with repositories
    repositories = [
        {"repositoryId": "test-repo", "name": "Test Repo"},
        {"repositoryId": "other-repo", "name": "Other Repo"},
    ]
    mock_aws_magicmock_services["ssm"].get_parameter.return_value = {"Parameter": {"Value": json.dumps(repositories)}}
    mock_aws_magicmock_services["ssm"].put_parameter.return_value = {}

    # Mock dependencies
    with patch("repository.lambda_functions.ssm_client", mock_aws_magicmock_services["ssm"]):
        # Should not raise any exception
        _remove_legacy("test-repo")

        # Should call put_parameter to update the list
        mock_aws_magicmock_services["ssm"].put_parameter.assert_called_once()


# Test validation functions
def test_validate_model_name():
    """Test validate_model_name function - REFACTORED VERSION."""
    from utilities.validation import validate_model_name, ValidationError

    # Test valid model name
    assert validate_model_name("embedding-model") is True

    # Test invalid model names
    with pytest.raises(ValidationError):
        validate_model_name(None)

    with pytest.raises(ValidationError):
        validate_model_name("")


# Test error scenarios
def test_similarity_search_missing_params(mock_auth_context, lambda_context):
    """Test similarity_search with missing parameters - REFACTORED VERSION."""
    from repository.lambda_functions import similarity_search

    # Test missing repositoryId
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    event["pathParameters"] = {}
    event["queryStringParameters"] = {"modelName": "test-model", "query": "test query"}

    response = similarity_search(event, lambda_context)

    # Should return error response due to missing repositoryId - KeyError returns 400
    assert response["statusCode"] == 400


def test_delete_documents_missing_params(mock_auth_context, mock_repository_services, lambda_context):
    """Test delete_documents with missing parameters - REFACTORED VERSION."""
    from repository.lambda_functions import delete_documents

    # Create test event with missing parameters
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    event["pathParameters"] = {"repositoryId": "test-repo"}
    event["body"] = "{}"  # No documentIds or documentName

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]):
        response = delete_documents(event, lambda_context)

    # Should return error response - ValidationError returns 400
    assert response["statusCode"] == 400


def test_list_jobs_function(mock_auth_context, mock_aws_services, mock_repository_services, lambda_context):
    """Test list_jobs function - REFACTORED VERSION."""
    from repository.lambda_functions import list_jobs

    # Create test event with proper groups structure
    event = RepositoryTestHelper.create_repository_event("test-user", ["test-group"])
    event["pathParameters"] = {"repositoryId": "test-repo"}
    event["queryStringParameters"] = {"pageSize": "10"}

    # Create mock job objects with model_dump method
    mock_job = MagicMock()
    mock_job.model_dump.return_value = {
        "jobId": "job-1",
        "status": "completed",
        "username": "test-user",
        "repositoryId": "test-repo",
    }

    # Set up mock ingestion job repository
    mock_ingestion_job_repo = MagicMock()
    mock_ingestion_job_repo.list_jobs_by_repository.return_value = ([mock_job], None)

    # Mock dependencies
    with patch("repository.lambda_functions.vs_repo", mock_repository_services["vs_repo"]), patch(
        "repository.lambda_functions.ingestion_job_repository", mock_ingestion_job_repo
    ), patch("repository.lambda_functions.ddb_client", mock_aws_services["dynamodb"]):

        response = list_jobs(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "jobs" in body
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["jobId"] == "job-1"
    assert body["jobs"][0]["status"] == "completed"
