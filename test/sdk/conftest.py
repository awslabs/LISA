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

"""Fixtures for lisa-sdk unit tests."""

import json
from pathlib import Path
from typing import Any

import pytest
import responses
from lisapy import LisaApi


@pytest.fixture
def api_url() -> str:
    """Base API URL for testing."""
    return "https://api.example.com/v1"


@pytest.fixture
def api_headers() -> dict[str, str]:
    """API headers for testing."""
    return {"Authorization": "Bearer test-token", "Content-Type": "application/json"}


@pytest.fixture
def lisa_api(api_url: str, api_headers: dict[str, str]) -> LisaApi:
    """Create a LisaApi instance for testing."""
    return LisaApi(url=api_url, headers=api_headers, verify=False)


@pytest.fixture
def mock_responses():
    """Activate responses mock for HTTP requests."""
    with responses.RequestsMock() as rsps:
        yield rsps


def load_fixture(filename: str) -> Any:
    """Load a JSON fixture file.

    Args:
        filename: Name of the fixture file (without .json extension)

    Returns:
        Parsed JSON data
    """
    fixture_path = Path(__file__).parent / "fixtures" / f"{filename}.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def mock_models_response() -> dict:
    """Mock response for list_models endpoint."""
    return {
        "models": [
            {
                "modelId": "anthropic.claude-v2",
                "modelName": "Claude v2",
                "modelType": "textgen",
                "streaming": True,
                "provider": "bedrock",
            },
            {
                "modelId": "amazon.titan-embed-text-v1",
                "modelName": "Titan Embeddings",
                "modelType": "embedding",
                "streaming": False,
                "provider": "bedrock",
            },
            {
                "modelId": "custom-llama-2",
                "modelName": "Llama 2 7B",
                "modelType": "textgen",
                "streaming": True,
                "provider": "ecs.textgen.tgi",
            },
        ]
    }


@pytest.fixture
def mock_repositories_response() -> list:
    """Mock response for list_repositories endpoint."""
    return [
        {
            "repositoryId": "pgvector-rag",
            "repositoryName": "PGVector RAG",
            "type": "pgvector",
            "embeddingModelId": "amazon.titan-embed-text-v1",
            "status": "ACTIVE",
            "createdAt": "2024-01-15T10:30:00Z",
        },
        {
            "repositoryId": "opensearch-rag",
            "repositoryName": "OpenSearch RAG",
            "type": "opensearch",
            "embeddingModelId": "amazon.titan-embed-text-v1",
            "status": "ACTIVE",
            "createdAt": "2024-01-16T14:20:00Z",
        },
    ]


@pytest.fixture
def mock_collections_response() -> dict:
    """Mock response for list_collections endpoint."""
    return {
        "collections": [
            {
                "collectionId": "col-123",
                "collectionName": "Test Collection",
                "repositoryId": "pgvector-rag",
                "embeddingModel": "amazon.titan-embed-text-v1",
                "status": "ACTIVE",
                "createdAt": "2024-01-20T09:00:00Z",
            },
            {
                "collectionId": "col-456",
                "collectionName": "Another Collection",
                "repositoryId": "pgvector-rag",
                "embeddingModel": "amazon.titan-embed-text-v1",
                "status": "ACTIVE",
                "createdAt": "2024-01-21T11:30:00Z",
            },
        ],
        "pagination": {"page": 1, "pageSize": 20, "totalItems": 2, "totalPages": 1},
    }


@pytest.fixture
def mock_documents_response() -> dict:
    """Mock response for list_documents endpoint."""
    return {
        "documents": [
            {
                "document_id": "doc-123",
                "document_name": "test-document.pdf",
                "collection_id": "col-123",
                "source": "s3://bucket/test-document.pdf",
                "status": "READY",
                "createdAt": "2024-01-22T10:00:00Z",
            },
            {
                "document_id": "doc-456",
                "document_name": "another-doc.txt",
                "collection_id": "col-123",
                "source": "s3://bucket/another-doc.txt",
                "status": "READY",
                "createdAt": "2024-01-22T11:00:00Z",
            },
        ],
        "lastEvaluated": None,
    }


@pytest.fixture
def mock_sessions_response() -> list:
    """Mock response for list_sessions endpoint."""
    return [
        {
            "sessionId": "sess-123",
            "userId": "user-1",
            "createdAt": "2024-01-23T08:00:00Z",
            "lastAccessedAt": "2024-01-23T09:30:00Z",
        },
        {
            "sessionId": "sess-456",
            "userId": "user-1",
            "createdAt": "2024-01-22T14:00:00Z",
            "lastAccessedAt": "2024-01-23T08:00:00Z",
        },
    ]


@pytest.fixture
def mock_configs_response() -> list:
    """Mock response for get_configs endpoint."""
    return [
        {"configScope": "global", "parameter": "maxTokens", "value": "4096"},
        {"configScope": "global", "parameter": "temperature", "value": "0.7"},
        {"configScope": "global", "parameter": "systemPrompt", "value": "You are a helpful assistant."},
    ]


@pytest.fixture
def mock_instances_response() -> list:
    """Mock response for list_instances endpoint."""
    return [
        "ml.g5.xlarge",
        "ml.g5.2xlarge",
        "ml.g5.4xlarge",
        "ml.p4d.24xlarge",
        "ml.inf2.xlarge",
    ]
