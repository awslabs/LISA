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
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import CollectionStatus, FixedChunkingStrategy, RagCollectionConfig


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("RAG_DOCUMENT_TABLE", "test-document-table")
    monkeypatch.setenv("RAG_SUB_DOCUMENT_TABLE", "test-sub-document-table")
    monkeypatch.setenv("LISA_RAG_VECTOR_STORE_TABLE", "test-vector-store-table")
    monkeypatch.setenv("LISA_RAG_COLLECTIONS_TABLE", "test-collections-table")
    monkeypatch.setenv("ADMIN_GROUP", "admin")  # Set admin group for authorization


def test_create_collection():
    """Test collection creation"""
    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
    )

    mock_repo.find_by_name.return_value = None  # No existing collection
    mock_repo.create.return_value = collection
    result = service.create_collection(collection, "user")

    assert result.collectionId == "test-coll"
    mock_repo.create.assert_called_once()


def test_get_collection():
    """Test get collection"""
    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    mock_repo.find_by_id.return_value = collection
    result = service.get_collection("test-repo", "test-coll", "user", ["group1"], False)

    assert result.collectionId == "test-coll"


def test_list_collections():
    """Test list collections"""

    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    # Mock repository with proper structure for service factory
    mock_repository = {
        "repositoryId": "test-repo",
        "type": "opensearch",
        "status": "CREATE_COMPLETE",
        "embeddingModelId": "model",
    }
    mock_vector_store_repo.find_repository_by_id.return_value = mock_repository
    mock_repo.list_by_repository.return_value = ([collection], None)

    result, key = service.list_collections("test-repo", "user", ["group1"], False)

    # Should return 2 collections: the test collection + default collection
    assert len(result) == 2
    # Find the test collection (not the default one)
    test_coll = [c for c in result if c.collectionId == "test-coll"][0]
    assert test_coll.collectionId == "test-coll"


def test_delete_collection():
    """Test delete regular collection (full deletion)"""
    from unittest.mock import patch

    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    mock_repo.find_by_id.return_value = collection
    mock_repo.update.return_value = None

    # Mock the dependencies created inside delete_collection
    mock_ingestion_job_repo = Mock()
    mock_ingestion_service = Mock()

    with patch("repository.collection_service.IngestionJobRepository", return_value=mock_ingestion_job_repo), patch(
        "repository.collection_service.DocumentIngestionService", return_value=mock_ingestion_service
    ):

        result = service.delete_collection(
            repository_id="test-repo",
            collection_id="test-coll",
            embedding_name=None,
            username="user",
            user_groups=["group1"],
            is_admin=False,
        )

    # Verify result contains deletion type
    assert result["deletionType"] == "full"
    assert "jobId" in result
    assert "status" in result

    # Verify status was updated to DELETE_IN_PROGRESS
    mock_repo.update.assert_called()
    # Verify ingestion job was saved and submitted
    mock_ingestion_job_repo.save.assert_called_once()
    mock_ingestion_service.create_delete_job.assert_called_once()


def test_delete_default_collection():
    """Test delete default collection (partial deletion)"""
    from unittest.mock import patch

    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    # Mock the dependencies created inside delete_collection
    mock_ingestion_job_repo = Mock()
    mock_ingestion_service = Mock()

    with patch("repository.collection_service.IngestionJobRepository", return_value=mock_ingestion_job_repo), patch(
        "repository.collection_service.DocumentIngestionService", return_value=mock_ingestion_service
    ):

        result = service.delete_collection(
            repository_id="test-repo",
            collection_id=None,
            embedding_name="test-embedding-model",
            username="user",
            user_groups=["group1"],
            is_admin=True,
        )

    # Verify result contains deletion type
    assert result["deletionType"] == "partial"
    assert "jobId" in result
    assert "status" in result

    # Verify status was NOT updated (no collection_id)
    mock_repo.update.assert_not_called()
    mock_repo.find_by_id.assert_not_called()

    # Verify ingestion job was saved and submitted
    mock_ingestion_job_repo.save.assert_called_once()
    mock_ingestion_service.create_delete_job.assert_called_once()

    # Verify the ingestion job has correct fields
    saved_job = mock_ingestion_job_repo.save.call_args[0][0]
    assert saved_job.collection_id is None
    assert saved_job.embedding_model == "test-embedding-model"
    assert saved_job.collection_deletion is True


def test_create_collection_lambda_with_embedding_model():
    """Test create_collection lambda with embedding model specified"""
    import json
    from unittest.mock import Mock, patch

    from repository.lambda_functions import create_collection

    event = {
        "requestContext": {
            "authorizer": {
                "username": "testuser",
                "groups": ["admin"],
            }
        },
        "pathParameters": {"repositoryId": "test-repo"},
        "body": json.dumps(
            {
                "name": "test-collection",
                "embeddingModel": "test-model",  # Collection has embedding model
                "chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 100},
                "metadata": {"tags": ["test"]},
            }
        ),
    }

    # Create mock context with required attributes
    mock_context = Mock()
    mock_context.function_name = "test-create-collection"

    mock_repository = {
        "repositoryId": "test-repo",
        "type": "opensearch",
        "allowedGroups": ["admin"],
        "embeddingModelId": None,  # No default embedding model
    }

    mock_collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="test-collection",
        embeddingModel="test-model",
        createdBy="testuser",
        status=CollectionStatus.ACTIVE,
    )

    with patch("repository.lambda_functions.get_repository") as mock_get_repo, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_service, patch("utilities.auth.is_admin") as mock_is_admin:

        mock_get_repo.return_value = mock_repository
        mock_service.create_collection.return_value = mock_collection
        mock_is_admin.return_value = True  # Mock admin check to pass

        result = create_collection(event, mock_context)

        # Should succeed - collection has embedding model
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["collectionId"] == "test-coll"
        assert body["embeddingModel"] == "test-model"

        # Verify collection service was called
        mock_service.create_collection.assert_called_once()


def test_create_collection_lambda_without_embedding_model_with_repository_default():
    """Test create_collection lambda without embedding model but repository has default"""
    import json
    from unittest.mock import Mock, patch

    from repository.lambda_functions import create_collection

    event = {
        "requestContext": {
            "authorizer": {
                "username": "testuser",
                "groups": ["admin"],
            }
        },
        "pathParameters": {"repositoryId": "test-repo"},
        "body": json.dumps(
            {
                "name": "test-collection",
                # No embeddingModel specified
                "chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 100},
                "metadata": {"tags": ["test"]},
            }
        ),
    }

    # Create mock context with required attributes
    mock_context = Mock()
    mock_context.function_name = "test-create-collection"

    mock_repository = {
        "repositoryId": "test-repo",
        "type": "opensearch",
        "allowedGroups": ["admin"],
        "embeddingModelId": "default-model",  # Repository has default embedding model
    }

    mock_collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="test-collection",
        embeddingModel=None,
        createdBy="testuser",
        status=CollectionStatus.ACTIVE,
    )

    with patch("repository.lambda_functions.get_repository") as mock_get_repo, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_service, patch("utilities.auth.is_admin") as mock_is_admin:

        mock_get_repo.return_value = mock_repository
        mock_service.create_collection.return_value = mock_collection
        mock_is_admin.return_value = True  # Mock admin check to pass

        result = create_collection(event, mock_context)

        # Should succeed - repository has default embedding model
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["collectionId"] == "test-coll"

        # Verify collection service was called
        mock_service.create_collection.assert_called_once()


def test_create_collection_lambda_without_embedding_model_no_repository_default():
    """Test create_collection lambda fails when no embedding model and no repository default"""
    import json
    from unittest.mock import Mock, patch

    from repository.lambda_functions import create_collection

    event = {
        "requestContext": {
            "authorizer": {
                "username": "testuser",
                "groups": ["admin"],
            }
        },
        "pathParameters": {"repositoryId": "test-repo"},
        "body": json.dumps(
            {
                "name": "test-collection",
                # No embeddingModel specified
                "chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 100},
                "metadata": {"tags": ["test"]},
            }
        ),
    }

    # Create mock context with required attributes
    mock_context = Mock()
    mock_context.function_name = "test-create-collection"

    mock_repository = {
        "repositoryId": "test-repo",
        "type": "opensearch",
        "allowedGroups": ["admin"],
        "embeddingModelId": None,  # No default embedding model
    }

    with patch("repository.lambda_functions.get_repository") as mock_get_repo, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_service, patch("utilities.auth.is_admin") as mock_is_admin:

        mock_get_repo.return_value = mock_repository
        mock_is_admin.return_value = True  # Mock admin check to pass

        result = create_collection(event, mock_context)

        # Should fail - no embedding model anywhere
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert (
            "Either the collection must specify an embeddingModel or "
            "the repository must have a default embeddingModelId"
        ) in body['error']

        # Verify collection service was NOT called
        mock_service.create_collection.assert_not_called()


def test_create_collection_lambda_original_payload():
    """Test create_collection lambda with the original failing payload"""
    import json
    from unittest.mock import Mock, patch

    from repository.lambda_functions import create_collection

    # Original payload that was failing
    event = {
        "requestContext": {
            "authorizer": {
                "username": "bedanley",
                "groups": ["admin"],
            }
        },
        "pathParameters": {"repositoryId": "test-repo"},
        "body": json.dumps(
            {"name": "rag-pv2-docs", "chunkingStrategy": {"type": "none"}, "metadata": {"tags": ["collection-tag"]}}
        ),
    }

    # Create mock context with required attributes
    mock_context = Mock()
    mock_context.function_name = "test-create-collection"

    mock_repository = {
        "repositoryId": "test-repo",
        "type": "opensearch",
        "allowedGroups": ["admin"],
        "embeddingModelId": "default-model",  # Repository has default embedding model
    }

    mock_collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="rag-pv2-docs",
        embeddingModel=None,
        createdBy="bedanley",
        status=CollectionStatus.ACTIVE,
    )

    with patch("repository.lambda_functions.get_repository") as mock_get_repo, patch(
        "repository.lambda_functions.collection_service"
    ) as mock_service, patch("utilities.auth.is_admin") as mock_is_admin:

        mock_get_repo.return_value = mock_repository
        mock_service.create_collection.return_value = mock_collection
        mock_is_admin.return_value = True  # Mock admin check to pass

        result = create_collection(event, mock_context)

        # Should succeed with repository default embedding model
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["name"] == "rag-pv2-docs"

        # Verify collection service was called
        mock_service.create_collection.assert_called_once()
