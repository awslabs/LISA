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

"""Unit tests for CollectionMixin."""

from typing import Dict

import pytest
import responses
from lisapy import LisaApi


class TestCollectionMixin:
    """Test suite for collection-related operations."""

    @responses.activate
    def test_create_collection(self, lisa_api: LisaApi, api_url: str):
        """Test creating a collection."""
        repo_id = "pgvector-rag"
        expected_response = {
            "collectionId": "col-new",
            "collectionName": "New Collection",
            "repositoryId": repo_id,
            "embeddingModel": "amazon.titan-embed-text-v1",
            "status": "ACTIVE",
            "createdAt": "2024-01-24T10:00:00Z",
        }

        responses.add(responses.POST, f"{api_url}/repository/{repo_id}/collection", json=expected_response, status=201)

        result = lisa_api.create_collection(
            repository_id=repo_id,
            name="New Collection",
            description="Test collection",
            embedding_model="amazon.titan-embed-text-v1",
        )

        assert result["collectionId"] == "col-new"
        assert result["collectionName"] == "New Collection"

    @responses.activate
    def test_create_collection_with_chunking_strategy(self, lisa_api: LisaApi, api_url: str):
        """Test creating a collection with custom chunking strategy."""
        repo_id = "pgvector-rag"
        chunking_strategy = {"type": "fixed", "size": 1024, "overlap": 102}

        expected_response = {
            "collectionId": "col-chunked",
            "collectionName": "Chunked Collection",
            "repositoryId": repo_id,
            "chunkingStrategy": chunking_strategy,
            "status": "ACTIVE",
            "createdAt": "2024-01-24T11:00:00Z",
        }

        responses.add(responses.POST, f"{api_url}/repository/{repo_id}/collection", json=expected_response, status=201)

        result = lisa_api.create_collection(
            repository_id=repo_id, name="Chunked Collection", chunking_strategy=chunking_strategy
        )

        assert result["collectionId"] == "col-chunked"
        assert result["chunkingStrategy"]["size"] == 1024

    @responses.activate
    def test_create_collection_with_metadata(self, lisa_api: LisaApi, api_url: str):
        """Test creating a collection with metadata."""
        repo_id = "pgvector-rag"
        metadata = {"tags": ["test", "demo"], "customFields": {"owner": "team-a"}}

        expected_response = {
            "collectionId": "col-meta",
            "collectionName": "Collection with Metadata",
            "repositoryId": repo_id,
            "metadata": metadata,
            "status": "ACTIVE",
            "createdAt": "2024-01-24T12:00:00Z",
        }

        responses.add(responses.POST, f"{api_url}/repository/{repo_id}/collection", json=expected_response, status=201)

        result = lisa_api.create_collection(
            repository_id=repo_id, name="Collection with Metadata", metadata=metadata, allowed_groups=["admin"]
        )

        assert result["collectionId"] == "col-meta"
        assert result["metadata"]["tags"] == ["test", "demo"]

    @responses.activate
    def test_get_collection(self, lisa_api: LisaApi, api_url: str):
        """Test getting a collection by ID."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"

        expected_response = {
            "collectionId": collection_id,
            "collectionName": "Test Collection",
            "repositoryId": repo_id,
            "status": "ACTIVE",
        }

        responses.add(
            responses.GET,
            f"{api_url}/repository/{repo_id}/collection/{collection_id}",
            json=expected_response,
            status=200,
        )

        result = lisa_api.get_collection(repo_id, collection_id)

        assert result["collectionId"] == collection_id
        assert result["collectionName"] == "Test Collection"

    @responses.activate
    def test_update_collection(self, lisa_api: LisaApi, api_url: str):
        """Test updating a collection."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"

        expected_response = {
            "collectionId": collection_id,
            "collectionName": "Updated Collection",
            "description": "Updated description",
            "repositoryId": repo_id,
            "status": "ACTIVE",
            "updatedAt": "2024-01-24T13:00:00Z",
        }

        responses.add(
            responses.PUT,
            f"{api_url}/repository/{repo_id}/collection/{collection_id}",
            json=expected_response,
            status=200,
        )

        result = lisa_api.update_collection(
            repository_id=repo_id,
            collection_id=collection_id,
            name="Updated Collection",
            description="Updated description",
        )

        assert result["collectionName"] == "Updated Collection"
        assert result["description"] == "Updated description"

    @responses.activate
    def test_update_collection_status(self, lisa_api: LisaApi, api_url: str):
        """Test updating collection status."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"

        expected_response = {
            "collectionId": collection_id,
            "collectionName": "Test Collection",
            "repositoryId": repo_id,
            "status": "ARCHIVED",
            "updatedAt": "2024-01-24T14:00:00Z",
        }

        responses.add(
            responses.PUT,
            f"{api_url}/repository/{repo_id}/collection/{collection_id}",
            json=expected_response,
            status=200,
        )

        result = lisa_api.update_collection(repository_id=repo_id, collection_id=collection_id, status="ARCHIVED")

        assert result["status"] == "ARCHIVED"

    @responses.activate
    def test_delete_collection(self, lisa_api: LisaApi, api_url: str):
        """Test deleting a collection."""
        repo_id = "pgvector-rag"
        collection_id = "col-old"

        responses.add(responses.DELETE, f"{api_url}/repository/{repo_id}/collection/{collection_id}", status=204)

        result = lisa_api.delete_collection(repo_id, collection_id)

        assert result is True
        assert len(responses.calls) == 1

    @responses.activate
    def test_list_collections(self, lisa_api: LisaApi, api_url: str, mock_collections_response: Dict):
        """Test listing collections in a repository."""
        repo_id = "pgvector-rag"

        responses.add(
            responses.GET, f"{api_url}/repository/{repo_id}/collections", json=mock_collections_response, status=200
        )

        result = lisa_api.list_collections(repo_id)

        assert "collections" in result
        assert len(result["collections"]) == 2
        assert result["collections"][0]["collectionId"] == "col-123"

    @responses.activate
    def test_list_collections_with_pagination(self, lisa_api: LisaApi, api_url: str):
        """Test listing collections with pagination."""
        repo_id = "pgvector-rag"
        page_response = {
            "collections": [{"collectionId": "col-1", "collectionName": "Collection 1"}],
            "pagination": {"page": 2, "pageSize": 10, "totalItems": 25, "totalPages": 3},
        }

        responses.add(responses.GET, f"{api_url}/repository/{repo_id}/collections", json=page_response, status=200)

        result = lisa_api.list_collections(repo_id, page=2, page_size=10)

        assert result["pagination"]["page"] == 2
        assert result["pagination"]["totalPages"] == 3

    @responses.activate
    def test_list_collections_with_filters(self, lisa_api: LisaApi, api_url: str):
        """Test listing collections with filters."""
        repo_id = "pgvector-rag"
        filtered_response = {
            "collections": [{"collectionId": "col-test", "collectionName": "Test Collection"}],
            "pagination": {"page": 1, "pageSize": 20, "totalItems": 1, "totalPages": 1},
        }

        responses.add(responses.GET, f"{api_url}/repository/{repo_id}/collections", json=filtered_response, status=200)

        result = lisa_api.list_collections(
            repo_id, filter_text="test", status_filter="active", sort_by="name", sort_order="asc"
        )

        assert len(result["collections"]) == 1
        assert "test" in result["collections"][0]["collectionName"].lower()

    @responses.activate
    def test_get_user_collections(self, lisa_api: LisaApi, api_url: str):
        """Test getting all collections user has access to."""
        user_collections_response = {
            "collections": [
                {"collectionId": "col-1", "repositoryId": "repo-1", "collectionName": "Collection 1"},
                {"collectionId": "col-2", "repositoryId": "repo-2", "collectionName": "Collection 2"},
            ]
        }

        responses.add(responses.GET, f"{api_url}/repository/collections", json=user_collections_response, status=200)

        result = lisa_api.get_user_collections()

        assert len(result) == 2
        assert result[0]["collectionId"] == "col-1"
        assert result[1]["repositoryId"] == "repo-2"

    @responses.activate
    def test_get_user_collections_with_filter(self, lisa_api: LisaApi, api_url: str):
        """Test getting user collections with filter."""
        filtered_response = {"collections": [{"collectionId": "col-test", "collectionName": "Test Collection"}]}

        responses.add(responses.GET, f"{api_url}/repository/collections", json=filtered_response, status=200)

        result = lisa_api.get_user_collections(filter_text="test", page_size=50)

        assert len(result) == 1
        assert "test" in result[0]["collectionName"].lower()

    @responses.activate
    def test_create_collection_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when creating a collection fails."""
        repo_id = "pgvector-rag"

        responses.add(
            responses.POST,
            f"{api_url}/repository/{repo_id}/collection",
            json={"error": "Invalid name"},
            status=400,
        )

        with pytest.raises(Exception):
            lisa_api.create_collection(repository_id=repo_id, name="")

    @responses.activate
    def test_get_collection_not_found(self, lisa_api: LisaApi, api_url: str):
        """Test getting a collection that doesn't exist."""
        repo_id = "pgvector-rag"
        collection_id = "non-existent"

        responses.add(
            responses.GET,
            f"{api_url}/repository/{repo_id}/collection/{collection_id}",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(Exception):
            lisa_api.get_collection(repo_id, collection_id)
