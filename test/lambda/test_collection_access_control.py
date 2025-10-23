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
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def mock_collection_repo():
    with patch("repository.collection_access_control.CollectionRepository") as mock:
        yield mock.return_value


@pytest.fixture
def mock_vector_store_repo():
    with patch("repository.collection_access_control.VectorStoreRepository") as mock:
        yield mock.return_value


def test_collection_policy_get_resource_context(mock_collection_repo, mock_vector_store_repo):
    from models.domain_objects import RagCollectionConfig
    from repository.collection_access_control import CollectionAccessControlPolicy

    mock_collection = MagicMock(spec=RagCollectionConfig)
    mock_collection.allowedGroups = ["group1"]
    mock_collection.createdBy = "user1"
    mock_collection.private = False
    mock_collection.status = "active"
    mock_collection_repo.find_by_id.return_value = mock_collection

    policy = CollectionAccessControlPolicy(mock_collection_repo, mock_vector_store_repo)
    context = policy.get_resource_context("coll1", repository_id="repo1")

    assert context is not None
    assert context.resource_id == "coll1"
    assert context.parent_id == "repo1"


def test_collection_policy_check_repository_access_admin(mock_collection_repo, mock_vector_store_repo):
    from repository.collection_access_control import CollectionAccessControlPolicy
    from utilities.access_control import Permission, UserContext

    policy = CollectionAccessControlPolicy(mock_collection_repo, mock_vector_store_repo)
    user = UserContext(user_id="admin", groups=[], is_admin=True)

    decision = policy.check_repository_access(user, "repo1", Permission.WRITE)
    assert decision.allowed


def test_collection_policy_check_repository_access_user_collections_disabled(
    mock_collection_repo, mock_vector_store_repo
):
    from repository.collection_access_control import CollectionAccessControlPolicy
    from utilities.access_control import Permission, UserContext

    mock_vector_store_repo.find_repository_by_id.return_value = {"allowUserCollections": False}
    policy = CollectionAccessControlPolicy(mock_collection_repo, mock_vector_store_repo)
    user = UserContext(user_id="user1", groups=["group1"], is_admin=False)

    decision = policy.check_repository_access(user, "repo1", Permission.WRITE)
    assert not decision.allowed


def test_collection_service_check_permission(mock_collection_repo, mock_vector_store_repo):
    from models.domain_objects import RagCollectionConfig
    from repository.collection_access_control import CollectionAccessControlService
    from utilities.access_control import Permission

    mock_collection = MagicMock(spec=RagCollectionConfig)
    mock_collection.allowedGroups = ["group1"]
    mock_collection.createdBy = "user1"
    mock_collection.private = False
    mock_collection.status = "active"
    mock_collection_repo.find_by_id.return_value = mock_collection

    service = CollectionAccessControlService(mock_collection_repo, mock_vector_store_repo)
    decision = service.check_collection_permission("user1", ["group1"], False, "coll1", "repo1", Permission.READ)
    assert decision.allowed


def test_check_collection_permission_function(mock_collection_repo, mock_vector_store_repo):
    from models.domain_objects import RagCollectionConfig
    from repository.collection_access_control import check_collection_permission
    from utilities.access_control import Permission

    mock_collection = MagicMock(spec=RagCollectionConfig)
    mock_collection.allowedGroups = ["group1"]
    mock_collection.createdBy = "user1"
    mock_collection.private = False
    mock_collection.status = "active"
    mock_collection_repo.find_by_id.return_value = mock_collection

    with patch("repository.collection_access_control.CollectionRepository", return_value=mock_collection_repo):
        with patch("repository.collection_access_control.VectorStoreRepository", return_value=mock_vector_store_repo):
            result = check_collection_permission("user1", ["group1"], False, "coll1", "repo1", Permission.READ)
            assert isinstance(result, bool)
