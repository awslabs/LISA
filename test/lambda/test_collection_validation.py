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

#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def mock_collection_repo():
    with patch("repository.collection_validation.CollectionRepository") as mock:
        yield mock.return_value


@pytest.fixture
def mock_vector_store_repo():
    with patch("repository.collection_validation.VectorStoreRepository") as mock:
        yield mock.return_value


def test_validate_name_valid(mock_collection_repo, mock_vector_store_repo):
    from repository.collection_validation import CollectionValidationService

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    service._validate_name("Valid Name 123")


def test_validate_name_empty(mock_collection_repo, mock_vector_store_repo):
    from repository.collection_validation import CollectionValidationService
    from utilities.validation import ValidationError

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    with pytest.raises(ValidationError):
        service._validate_name("")


def test_validate_name_too_long(mock_collection_repo, mock_vector_store_repo):
    from repository.collection_validation import CollectionValidationService
    from utilities.validation import ValidationError

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    with pytest.raises(ValidationError):
        service._validate_name("a" * 101)


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


def test_validate_chunking_strategy_fixed_size(mock_collection_repo, mock_vector_store_repo):
    from models.domain_objects import FixedSizeChunkingStrategy
    from repository.collection_validation import CollectionValidationService

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    strategy = FixedSizeChunkingStrategy(chunkSize=500, chunkOverlap=50)
    service._validate_chunking_strategy(strategy)


def test_validate_metadata(mock_collection_repo, mock_vector_store_repo):
    from models.domain_objects import CollectionMetadata
    from repository.collection_validation import CollectionValidationService

    service = CollectionValidationService(mock_collection_repo, mock_vector_store_repo)
    metadata = CollectionMetadata(tags=["tag1", "tag2"])
    service._validate_metadata(metadata)


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


def test_validate_collection_name_function():
    from repository.collection_validation import validate_collection_name

    assert validate_collection_name("Valid Name")


def test_validate_groups_subset_function():
    from repository.collection_validation import validate_groups_subset

    assert validate_groups_subset(["group1"], ["group1", "group2"])
