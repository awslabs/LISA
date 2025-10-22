#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import CollectionStatus, FixedSizeChunkingStrategy, RagCollectionConfig


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_can_access_collection_admin():
    """Test admin can access collection"""
    from repository.collection_access_control_helpers import can_access_collection

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="other",
        status=CollectionStatus.ACTIVE,
        private=True,
    )

    result = can_access_collection(collection, "admin", ["group2"], True)
    assert result is True


def test_can_access_collection_owner():
    """Test owner can access private collection"""
    from repository.collection_access_control_helpers import can_access_collection

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        private=True,
    )

    result = can_access_collection(collection, "user1", ["group2"], False)
    assert result is True


def test_can_access_collection_group():
    """Test user can access via group"""
    from repository.collection_access_control_helpers import can_access_collection

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="other",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    result = can_access_collection(collection, "user1", ["group1"], False)
    assert result is True


def test_can_access_collection_denied():
    """Test user cannot access collection"""
    from repository.collection_access_control_helpers import can_access_collection

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="other",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    result = can_access_collection(collection, "user1", ["group2"], False)
    assert result is False


def test_validate_collection_access_allowed():
    """Test validate collection access allowed"""
    from repository.collection_access_control_helpers import validate_collection_access

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    # Should not raise exception
    validate_collection_access(collection, "user1", ["group1"], False)


def test_validate_collection_access_denied():
    """Test validate collection access denied"""
    from repository.collection_access_control_helpers import validate_collection_access
    from utilities.validation import ValidationError

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="other",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    with pytest.raises(ValidationError, match="Permission denied"):
        validate_collection_access(collection, "user1", ["group2"], False)


def test_can_modify_collection_admin():
    """Test admin can modify collection"""
    from repository.collection_access_control_helpers import can_modify_collection

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="other",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    result = can_modify_collection(collection, "admin", True)
    assert result is True


def test_can_modify_collection_owner():
    """Test owner can modify collection"""
    from repository.collection_access_control_helpers import can_modify_collection

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    result = can_modify_collection(collection, "user1", False)
    assert result is True


def test_can_modify_collection_denied():
    """Test non-owner cannot modify collection"""
    from repository.collection_access_control_helpers import can_modify_collection

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
        allowedGroups=["group1"],
        createdBy="other",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    result = can_modify_collection(collection, "user1", False)
    assert result is False
