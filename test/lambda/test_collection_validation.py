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
from unittest.mock import patch

import pytest
from pydantic import ValidationError as PydanticValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def mock_collection_repo():
    with patch("repository.collection_validation.CollectionRepository") as mock:
        yield mock.return_value


@pytest.fixture
def mock_vector_store_repo():
    with patch("repository.collection_validation.VectorStoreRepository") as mock:
        yield mock.return_value


# Pydantic validation tests for domain objects
def test_create_collection_request_name_valid():
    from models.domain_objects import CreateCollectionRequest

    request = CreateCollectionRequest(name="Valid Name 123")
    assert request.name == "Valid Name 123"


def test_create_collection_request_name_empty():
    from models.domain_objects import CreateCollectionRequest

    with pytest.raises(PydanticValidationError):
        CreateCollectionRequest(name="")


def test_create_collection_request_name_invalid_chars():
    from models.domain_objects import CreateCollectionRequest

    with pytest.raises(PydanticValidationError):
        CreateCollectionRequest(name="Invalid@Name!")


def test_create_collection_request_name_too_long():
    from models.domain_objects import CreateCollectionRequest

    with pytest.raises(PydanticValidationError):
        CreateCollectionRequest(name="a" * 101)


def test_update_collection_request_name_valid():
    from models.domain_objects import UpdateCollectionRequest

    request = UpdateCollectionRequest(name="Valid Name")
    assert request.name == "Valid Name"


def test_update_collection_request_name_invalid():
    from models.domain_objects import UpdateCollectionRequest

    with pytest.raises(PydanticValidationError):
        UpdateCollectionRequest(name="Invalid@Name")


def test_fixed_chunking_strategy_valid():
    from models.domain_objects import FixedChunkingStrategy

    strategy = FixedChunkingStrategy(size=500, overlap=50)
    assert strategy.size == 500
    assert strategy.overlap == 50


def test_fixed_chunking_strategy_size_too_small():
    from models.domain_objects import FixedChunkingStrategy

    with pytest.raises(PydanticValidationError):
        FixedChunkingStrategy(size=50, overlap=10)


def test_fixed_chunking_strategy_size_too_large():
    from models.domain_objects import FixedChunkingStrategy

    with pytest.raises(PydanticValidationError):
        FixedChunkingStrategy(size=20000, overlap=100)


def test_fixed_chunking_strategy_overlap_negative():
    from models.domain_objects import FixedChunkingStrategy

    with pytest.raises(PydanticValidationError):
        FixedChunkingStrategy(size=500, overlap=-10)


def test_fixed_chunking_strategy_overlap_too_large():
    from models.domain_objects import FixedChunkingStrategy

    with pytest.raises(PydanticValidationError):
        FixedChunkingStrategy(size=500, overlap=300)


def test_collection_metadata_tags_valid():
    from models.domain_objects import CollectionMetadata

    metadata = CollectionMetadata(tags=["tag1", "tag-2", "tag_3"])
    assert len(metadata.tags) == 3


def test_collection_metadata_tags_too_many():
    from models.domain_objects import CollectionMetadata

    with pytest.raises(PydanticValidationError):
        CollectionMetadata(tags=[f"tag{i}" for i in range(51)])


def test_collection_metadata_tag_too_long():
    from models.domain_objects import CollectionMetadata

    with pytest.raises(PydanticValidationError):
        CollectionMetadata(tags=["a" * 51])


def test_collection_metadata_tag_invalid_chars():
    from models.domain_objects import CollectionMetadata

    with pytest.raises(PydanticValidationError):
        CollectionMetadata(tags=["invalid@tag"])


# Repository-specific validation tests
def test_validate_allowed_groups_subset(mock_collection_repo, mock_vector_store_repo):
    from repository.collection_validation import CollectionValidationService

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    service._validate_allowed_groups(["group1"], ["group1", "group2"])


def test_validate_allowed_groups_not_subset(mock_collection_repo, mock_vector_store_repo):
    from repository.collection_validation import CollectionValidationService
    from utilities.validation import ValidationError

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    with pytest.raises(ValidationError):
        service._validate_allowed_groups(["group3"], ["group1", "group2"])


def test_validate_create_request(mock_collection_repo, mock_vector_store_repo):
    from models.domain_objects import CreateCollectionRequest
    from repository.collection_validation import CollectionValidationService

    mock_collection_repo.find_by_name.return_value = None
    mock_vector_store_repo.find_repository_by_id.return_value = {"allowedGroups": ["group1"]}

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    request = CreateCollectionRequest(name="Test Collection", allowedGroups=["group1"])
    result = service.validate_create_request(request, "repo1")
    assert result["valid"]


def test_validate_update_request(mock_collection_repo, mock_vector_store_repo):
    from models.domain_objects import UpdateCollectionRequest
    from repository.collection_validation import CollectionValidationService

    mock_collection_repo.find_by_name.return_value = None

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    request = UpdateCollectionRequest(name="Updated Name")
    result = service.validate_update_request(request, "coll1", "repo1")
    assert result["valid"]


def test_validate_groups_subset_function():
    from repository.collection_validation import validate_groups_subset

    assert validate_groups_subset(["group1"], ["group1", "group2"])
