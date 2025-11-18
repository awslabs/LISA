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

"""Unit tests for MetadataGenerator."""

import json
from unittest.mock import create_autospec, MagicMock

import pytest
from models.domain_objects import CollectionMetadata, RagCollectionConfig
from repository.metadata_generator import MetadataGenerator
from utilities.validation import ValidationError


@pytest.fixture
def mock_cloudwatch():
    """Mock CloudWatch client."""
    return create_autospec(MagicMock, instance=True)


@pytest.fixture
def metadata_generator(mock_cloudwatch):
    """Create MetadataGenerator instance with mocked CloudWatch."""
    return MetadataGenerator(cloudwatch_client=mock_cloudwatch)


@pytest.fixture
def sample_repository():
    """Sample repository configuration."""
    return {
        "repositoryId": "repo-123",
        "repositoryName": "Test Repository",
        "metadata": {
            "tags": ["engineering"],
            "customFields": {"department": "Engineering"},
        },
    }


@pytest.fixture
def sample_collection():
    """Sample collection configuration."""
    return RagCollectionConfig(
        collectionId="col-456",
        repositoryId="repo-123",
        name="Test Collection",
        createdBy="test-user",
        embeddingModel="amazon.titan-embed-text-v1",
        metadata=CollectionMetadata(tags=["api", "documentation"], customFields={"classification": "internal"}),
    )


def test_generate_metadata_json_with_all_sources(metadata_generator, sample_repository, sample_collection):
    """Test metadata generation with repository, collection, and document metadata."""
    document_metadata = {"author": "John Doe", "version": "1.0"}

    result = metadata_generator.generate_metadata_json(
        repository=sample_repository, collection=sample_collection, document_metadata=document_metadata
    )

    # Verify structure
    assert "metadataAttributes" in result
    metadata = result["metadataAttributes"]

    # Verify repository metadata
    assert metadata["department"] == "Engineering"
    assert metadata["tag_engineering"] is True

    # Verify collection metadata
    assert metadata["collectionId"] == "col-456"
    assert metadata["collectionName"] == "Test Collection"
    assert metadata["classification"] == "internal"
    assert metadata["tag_api"] is True
    assert metadata["tag_documentation"] is True

    # Verify document metadata (highest precedence)
    assert metadata["author"] == "John Doe"
    assert metadata["version"] == "1.0"

    # Verify repository ID
    assert metadata["repositoryId"] == "repo-123"


def test_generate_metadata_json_precedence(metadata_generator, sample_repository, sample_collection):
    """Test that document metadata overrides collection and repository metadata."""
    # Add conflicting field in repository
    sample_repository["metadata"]["customFields"]["classification"] = "public"

    # Document metadata should override
    document_metadata = {"classification": "confidential"}

    result = metadata_generator.generate_metadata_json(
        repository=sample_repository, collection=sample_collection, document_metadata=document_metadata
    )

    metadata = result["metadataAttributes"]
    # Document metadata wins
    assert metadata["classification"] == "confidential"


def test_generate_metadata_json_without_collection(metadata_generator, sample_repository):
    """Test metadata generation without collection."""
    result = metadata_generator.generate_metadata_json(repository=sample_repository, collection=None)

    metadata = result["metadataAttributes"]
    assert metadata["department"] == "Engineering"
    assert metadata["repositoryId"] == "repo-123"
    assert "collectionId" not in metadata


def test_generate_metadata_json_without_document_metadata(metadata_generator, sample_repository, sample_collection):
    """Test metadata generation without document-specific metadata."""
    result = metadata_generator.generate_metadata_json(
        repository=sample_repository, collection=sample_collection, document_metadata=None
    )

    metadata = result["metadataAttributes"]
    assert metadata["department"] == "Engineering"
    assert metadata["collectionId"] == "col-456"


def test_validate_metadata_success(metadata_generator):
    """Test successful metadata validation."""
    metadata = {"key1": "value1", "key2": 123, "key3": True, "key4": ["item1", "item2"]}

    assert metadata_generator.validate_metadata(metadata) is True


def test_validate_metadata_invalid_key_characters(metadata_generator):
    """Test validation fails for invalid key characters."""
    metadata = {"invalid key!": "value"}

    with pytest.raises(ValidationError) as exc_info:
        metadata_generator.validate_metadata(metadata)

    assert "invalid characters" in str(exc_info.value).lower()


def test_validate_metadata_key_too_long(metadata_generator):
    """Test validation fails for key exceeding max length."""
    long_key = "a" * 101  # MAX_METADATA_KEY_LENGTH is 100
    metadata = {long_key: "value"}

    with pytest.raises(ValidationError) as exc_info:
        metadata_generator.validate_metadata(metadata)

    assert "exceeds maximum length" in str(exc_info.value).lower()


def test_validate_metadata_reserved_field(metadata_generator):
    """Test validation fails for reserved Bedrock KB fields."""
    metadata = {"x-amz-bedrock-kb-source-uri": "value"}

    with pytest.raises(ValidationError) as exc_info:
        metadata_generator.validate_metadata(metadata)

    assert "reserved" in str(exc_info.value).lower()


def test_validate_metadata_invalid_value_type(metadata_generator):
    """Test validation fails for invalid value types."""
    metadata = {"key": {"nested": "object"}}  # Nested objects not allowed

    with pytest.raises(ValidationError) as exc_info:
        metadata_generator.validate_metadata(metadata)

    assert "invalid type" in str(exc_info.value).lower()


def test_validate_metadata_value_too_long(metadata_generator):
    """Test validation fails for value exceeding max length."""
    long_value = "a" * 1001  # MAX_METADATA_VALUE_LENGTH is 1000
    metadata = {"key": long_value}

    with pytest.raises(ValidationError) as exc_info:
        metadata_generator.validate_metadata(metadata)

    assert "exceeds maximum length" in str(exc_info.value).lower()


def test_validate_metadata_size_limit(metadata_generator):
    """Test validation fails when total metadata size exceeds limit."""
    # Create metadata that exceeds 10KB
    large_metadata = {f"key{i}": "x" * 100 for i in range(200)}

    with pytest.raises(ValidationError) as exc_info:
        metadata_generator.validate_metadata(large_metadata)

    assert "exceeds limit" in str(exc_info.value).lower()


def test_validate_metadata_array_with_invalid_element(metadata_generator):
    """Test validation fails for array with invalid element type."""
    metadata = {"key": ["valid", {"invalid": "object"}]}

    with pytest.raises(ValidationError) as exc_info:
        metadata_generator.validate_metadata(metadata)

    assert "invalid type" in str(exc_info.value).lower()


def test_get_metadata_s3_key(metadata_generator):
    """Test S3 key generation for metadata files."""
    document_key = "documents/test.pdf"
    metadata_key = metadata_generator.get_metadata_s3_key(document_key)

    assert metadata_key == "documents/test.pdf.metadata.json"


def test_get_metadata_s3_key_with_nested_path(metadata_generator):
    """Test S3 key generation for nested paths."""
    document_key = "folder1/folder2/document.docx"
    metadata_key = metadata_generator.get_metadata_s3_key(document_key)

    assert metadata_key == "folder1/folder2/document.docx.metadata.json"


def test_cache_functionality(metadata_generator):
    """Test metadata caching works correctly."""
    collection_id = "col-123"
    repository_id = "repo-456"

    # Mock collection repo
    mock_collection_repo = MagicMock()
    mock_collection = MagicMock()
    mock_collection.metadata = CollectionMetadata(tags=["test"], customFields={"field": "value"})
    mock_collection_repo.find_by_id.return_value = mock_collection

    # First call - should fetch from repo
    result1 = metadata_generator.get_collection_metadata_cached(collection_id, repository_id, mock_collection_repo)
    assert result1 is not None
    assert mock_collection_repo.find_by_id.call_count == 1

    # Second call - should use cache
    result2 = metadata_generator.get_collection_metadata_cached(collection_id, repository_id, mock_collection_repo)
    assert result2 is not None
    assert mock_collection_repo.find_by_id.call_count == 1  # Not called again


def test_clear_cache_specific_collection(metadata_generator):
    """Test clearing cache for specific collection."""
    # Add something to cache
    metadata_generator._collection_cache["repo-123#col-456"] = {"metadata": {}, "timestamp": 0}

    # Clear specific collection
    metadata_generator.clear_cache(collection_id="col-456", repository_id="repo-123")

    assert "repo-123#col-456" not in metadata_generator._collection_cache


def test_clear_cache_all(metadata_generator):
    """Test clearing all cache."""
    # Add multiple items to cache
    metadata_generator._collection_cache["repo-1#col-1"] = {"metadata": {}, "timestamp": 0}
    metadata_generator._collection_cache["repo-2#col-2"] = {"metadata": {}, "timestamp": 0}

    # Clear all
    metadata_generator.clear_cache()

    assert len(metadata_generator._collection_cache) == 0
