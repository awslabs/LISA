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


import pytest
from models.domain_objects import CollectionMetadata, RagCollectionConfig
from repository.metadata_generator import MetadataGenerator
from utilities.validation import ValidationError


@pytest.fixture
def sample_repository():
    """Sample repository configuration."""
    return {
        "repositoryId": "repo-123",
        "repositoryName": "Test Repository",
        "metadata": {
            "tags": ["engineering"],
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
        metadata=CollectionMetadata(tags=["api", "documentation"]),
    )


def test_generate_metadata_json_with_all_sources(sample_repository, sample_collection):
    """Test metadata generation with repository, collection, and document metadata."""
    document_metadata = {"author": "John Doe", "version": "1.0"}

    result = MetadataGenerator.generate_metadata_json(
        repository=sample_repository, collection=sample_collection, document_metadata=document_metadata
    )

    # Verify structure
    assert "metadataAttributes" in result
    metadata = result["metadataAttributes"]

    # Verify repository metadata (tags only, customFields removed)
    assert metadata["tag_engineering"] is True

    # Verify collection metadata
    assert metadata["collectionId"] == "col-456"
    assert metadata["tag_api"] is True
    assert metadata["tag_documentation"] is True

    # Verify document metadata (highest precedence)
    assert metadata["author"] == "John Doe"
    assert metadata["version"] == "1.0"

    # Verify repository ID
    assert metadata["repositoryId"] == "repo-123"


def test_generate_metadata_json_precedence(sample_repository, sample_collection):
    """Test that document metadata is included in generated metadata."""
    # Document metadata should be included
    document_metadata = {"classification": "confidential"}

    result = MetadataGenerator.generate_metadata_json(
        repository=sample_repository, collection=sample_collection, document_metadata=document_metadata
    )

    metadata = result["metadataAttributes"]
    # Document metadata is included
    assert metadata["classification"] == "confidential"


def test_generate_metadata_json_without_collection(sample_repository):
    """Test metadata generation without collection."""
    result = MetadataGenerator.generate_metadata_json(repository=sample_repository, collection=None)

    metadata = result["metadataAttributes"]
    assert metadata["tag_engineering"] is True
    assert metadata["repositoryId"] == "repo-123"
    assert "collectionId" not in metadata


def test_generate_metadata_json_without_document_metadata(sample_repository, sample_collection):
    """Test metadata generation without document-specific metadata."""
    result = MetadataGenerator.generate_metadata_json(
        repository=sample_repository, collection=sample_collection, document_metadata=None
    )

    metadata = result["metadataAttributes"]
    assert metadata["tag_engineering"] is True
    assert metadata["collectionId"] == "col-456"


def test_validate_metadata_success():
    """Test successful metadata validation."""
    metadata = {"key1": "value1", "key2": 123, "key3": True, "key4": ["item1", "item2"]}

    assert MetadataGenerator.validate_metadata(metadata) is True


def test_validate_metadata_invalid_key_characters():
    """Test validation fails for invalid key characters."""
    metadata = {"invalid key!": "value"}

    with pytest.raises(ValidationError) as exc_info:
        MetadataGenerator.validate_metadata(metadata)

    assert "invalid characters" in str(exc_info.value).lower()


def test_validate_metadata_key_too_long():
    """Test validation fails for key exceeding max length."""
    long_key = "a" * 101  # MAX_METADATA_KEY_LENGTH is 100
    metadata = {long_key: "value"}

    with pytest.raises(ValidationError) as exc_info:
        MetadataGenerator.validate_metadata(metadata)

    assert "exceeds maximum length" in str(exc_info.value).lower()


def test_validate_metadata_reserved_field():
    """Test validation fails for reserved Bedrock KB fields."""
    metadata = {"x-amz-bedrock-kb-source-uri": "value"}

    with pytest.raises(ValidationError) as exc_info:
        MetadataGenerator.validate_metadata(metadata)

    assert "reserved" in str(exc_info.value).lower()


def test_validate_metadata_invalid_value_type():
    """Test validation fails for invalid value types."""
    metadata = {"key": {"nested": "object"}}  # Nested objects not allowed

    with pytest.raises(ValidationError) as exc_info:
        MetadataGenerator.validate_metadata(metadata)

    assert "invalid type" in str(exc_info.value).lower()


def test_validate_metadata_value_too_long():
    """Test validation fails for value exceeding max length."""
    long_value = "a" * 1001  # MAX_METADATA_VALUE_LENGTH is 1000
    metadata = {"key": long_value}

    with pytest.raises(ValidationError) as exc_info:
        MetadataGenerator.validate_metadata(metadata)

    assert "exceeds maximum length" in str(exc_info.value).lower()


def test_validate_metadata_size_limit():
    """Test validation fails when total metadata size exceeds limit."""
    # Create metadata that exceeds 10KB
    large_metadata = {f"key{i}": "x" * 100 for i in range(200)}

    with pytest.raises(ValidationError) as exc_info:
        MetadataGenerator.validate_metadata(large_metadata)

    assert "exceeds limit" in str(exc_info.value).lower()


def test_validate_metadata_array_with_invalid_element():
    """Test validation fails for array with invalid element type."""
    metadata = {"key": ["valid", {"invalid": "object"}]}

    with pytest.raises(ValidationError) as exc_info:
        MetadataGenerator.validate_metadata(metadata)

    assert "invalid type" in str(exc_info.value).lower()


def test_merge_metadata_for_ingestion_jobs():
    """Test merge_metadata with for_bedrock_kb=False (ingestion job format)."""
    repository = {
        "repositoryId": "repo-123",
        "metadata": {"tags": ["repo-tag1", "repo-tag2"], "owner": "repository-owner", "environment": "test"},
    }

    collection = {
        "collectionId": "col-456",
        "name": "Test Collection",
        "metadata": {
            "tags": ["collection-tag1", "repo-tag1"],  # repo-tag1 should be deduplicated
            "purpose": "testing",
            "environment": "staging",  # Should override repository environment
        },
    }

    document_metadata = {
        "tags": ["document-tag1"],
        "author": "test-author",
        "environment": "production",  # Should override both repository and collection
    }

    result = MetadataGenerator.merge_metadata(
        repository=repository,
        collection=collection,
        document_metadata=document_metadata,
        for_bedrock_kb=False,  # Keep tags as array
    )

    # Verify tags are merged as array (no duplicates)
    expected_tags = ["repo-tag1", "repo-tag2", "collection-tag1", "document-tag1"]
    actual_tags = result.get("tags", [])
    assert sorted(actual_tags) == sorted(expected_tags)

    # Verify precedence: document > collection > repository
    assert result["environment"] == "production"  # Document overrides
    assert result["purpose"] == "testing"  # Collection metadata
    assert result["owner"] == "repository-owner"  # Repository metadata
    assert result["author"] == "test-author"  # Document metadata

    # Verify identifiers are added
    assert result["repositoryId"] == "repo-123"
    assert result["collectionId"] == "col-456"


def test_merge_metadata_for_bedrock_kb():
    """Test merge_metadata with for_bedrock_kb=True (Bedrock KB format)."""
    repository = {
        "repositoryId": "repo-123",
        "metadata": {"tags": ["repo-tag1", "repo-tag2"], "owner": "repository-owner"},
    }

    collection = {
        "collectionId": "col-456",
        "name": "Test Collection",
        "metadata": {"tags": ["collection-tag1"], "purpose": "testing"},
    }

    document_metadata = {"tags": ["document-tag1"], "author": "test-author"}

    result = MetadataGenerator.merge_metadata(
        repository=repository,
        collection=collection,
        document_metadata=document_metadata,
        for_bedrock_kb=True,  # Format for Bedrock KB
    )

    # Verify individual tag fields are created
    assert result["tag_repo-tag1"] is True
    assert result["tag_repo-tag2"] is True
    assert result["tag_collection-tag1"] is True
    assert result["tag_document-tag1"] is True

    # Verify comma-separated tags field
    expected_tags_str = "collection-tag1,document-tag1,repo-tag1,repo-tag2"
    assert result["tags"] == expected_tags_str

    # Verify other metadata
    assert result["owner"] == "repository-owner"
    assert result["purpose"] == "testing"
    assert result["author"] == "test-author"

    # Verify identifiers
    assert result["repositoryId"] == "repo-123"
    assert result["collectionId"] == "col-456"


def test_merge_metadata_without_collection():
    """Test merge_metadata without collection."""
    repository = {"repositoryId": "repo-123", "metadata": {"tags": ["repo-tag1"], "owner": "repository-owner"}}

    document_metadata = {"tags": ["document-tag1"], "author": "test-author"}

    result = MetadataGenerator.merge_metadata(
        repository=repository,
        collection=None,
        document_metadata=document_metadata,
        for_bedrock_kb=False,
    )

    # Verify tags are merged
    expected_tags = ["repo-tag1", "document-tag1"]
    actual_tags = result.get("tags", [])
    assert sorted(actual_tags) == sorted(expected_tags)

    # Verify metadata
    assert result["owner"] == "repository-owner"
    assert result["author"] == "test-author"
    assert result["repositoryId"] == "repo-123"

    # Collection fields should be empty
    assert result["collectionId"] == "default"


def test_merge_metadata_empty_inputs():
    """Test merge_metadata with minimal inputs."""
    repository = {"repositoryId": "repo-123"}

    result = MetadataGenerator.merge_metadata(
        repository=repository,
        collection=None,
        document_metadata=None,
        for_bedrock_kb=False,
    )

    # Should have at least repository ID
    assert result["repositoryId"] == "repo-123"
    assert result["collectionId"] == "default"

    # No tags should be present
    assert "tags" not in result or result["tags"] == []
