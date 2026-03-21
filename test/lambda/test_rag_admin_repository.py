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

"""Tests for RAG Admin authorization boundaries in repository lambda functions.

Uses the conftest mock_auth fixture for get_username/get_groups/get_user_context/is_admin,
but patches is_rag_admin directly on the repository.lambda_functions module.

Note: The conftest patches decorators (admin_only, rag_admin_or_admin) as passthroughs
when test_repository_lambda.py runs first (module-level import). So these tests focus on
the inner function logic: group access filtering, effective_admin, field restrictions,
and document ownership bypass.
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


ACCESSIBLE_REPO = {
    "repositoryId": "repo-1",
    "name": "Accessible Repo",
    "type": "pgvector",
    "allowedGroups": ["rag-team"],
    "status": "CREATE_COMPLETE",
    "embeddingModelId": "model-1",
    "pipelines": [{"collectionId": "coll-1", "s3Bucket": "bucket", "s3Prefix": "prefix", "trigger": "event",
                    "autoRemove": True, "chunkSize": 1000, "chunkOverlap": 100}],
}

INACCESSIBLE_REPO = {
    "repositoryId": "repo-2",
    "name": "Inaccessible Repo",
    "type": "pgvector",
    "allowedGroups": ["other-team"],
    "status": "CREATE_COMPLETE",
    "embeddingModelId": "model-2",
}


@pytest.fixture
def ctx():
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


def _make_event(username="test-user", groups=None):
    return {
        "requestContext": {
            "authorizer": {
                "username": username,
                "groups": json.dumps(groups or []),
            }
        },
    }


def _patch_auth(username, groups, is_admin_val, is_rag_admin_val):
    """Patch all auth references on the repository.lambda_functions module.

    Because repository.lambda_functions uses `from utilities.auth import ...`,
    the module has local bindings that must be patched directly (not on utilities.auth).
    """
    return [
        patch("repository.lambda_functions.get_username", return_value=username),
        patch("repository.lambda_functions.get_groups", return_value=groups),
        patch("repository.lambda_functions.is_admin", return_value=is_admin_val),
        patch("repository.lambda_functions.is_rag_admin", return_value=is_rag_admin_val),
        patch("repository.lambda_functions.get_user_context", return_value=(username, is_admin_val, groups)),
    ]


from contextlib import ExitStack


def _auth_context(username, groups, is_admin_val=False, is_rag_admin_val=False):
    """Context manager that patches all auth on repository.lambda_functions."""
    stack = ExitStack()
    for p in _patch_auth(username, groups, is_admin_val, is_rag_admin_val):
        stack.enter_context(p)
    return stack


# --- Collection CRUD: RAG Admin with group access ---


def test_rag_admin_can_create_collection_on_accessible_repo(mock_auth, ctx):
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"name": "New Collection", "embeddingModel": "model-1"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs, \
         patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "new-coll", "name": "New Collection"}
        mcs.create_collection.return_value = mock_coll

        from repository.lambda_functions import create_collection
        result = create_collection(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["collectionId"] == "new-coll"


def test_rag_admin_cannot_create_collection_on_inaccessible_repo(mock_auth, ctx):
    """RAG Admin without group access is denied by get_repository."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-2"}
    event["body"] = json.dumps({"name": "New Collection", "embeddingModel": "model-2"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs:
        mvs.find_repository_by_id.return_value = INACCESSIBLE_REPO

        from repository.lambda_functions import create_collection
        result = create_collection(event, ctx)

    assert result["statusCode"] == 403


def test_rag_admin_can_update_collection_on_accessible_repo(mock_auth, ctx):
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    event["body"] = json.dumps({"name": "Updated Collection"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs, \
         patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "coll-1", "name": "Updated Collection"}
        mcs.update_collection.return_value = mock_coll

        from repository.lambda_functions import update_collection
        result = update_collection(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["name"] == "Updated Collection"


def test_rag_admin_can_delete_collection_on_accessible_repo(mock_auth, ctx):
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    event["queryStringParameters"] = {}

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs, \
         patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mcs.delete_collection.return_value = {"deleted": True}

        from repository.lambda_functions import delete_collection
        result = delete_collection(event, ctx)

    assert result["statusCode"] == 200


# --- effective_admin: RAG Admin gets is_admin=True in collection_service ---


def test_rag_admin_passes_effective_admin_to_collection_service(mock_auth, ctx):
    """Verify collection_service.update_collection receives is_admin=True for RAG admins."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    event["body"] = json.dumps({"name": "Updated"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs, \
         patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "coll-1"}
        mcs.update_collection.return_value = mock_coll

        from repository.lambda_functions import update_collection
        update_collection(event, ctx)

        call_kwargs = mcs.update_collection.call_args[1]
        assert call_kwargs["is_admin"] is True


def test_regular_user_passes_is_admin_false_to_collection_service(mock_auth, ctx):
    """Verify collection_service receives is_admin=False for regular users."""
    mock_auth.set_user(username="regular-user", groups=["rag-team"], is_admin=False, is_rag_admin=False)
    event = _make_event("regular-user", ["rag-team"])
    event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    event["body"] = json.dumps({"name": "Updated"})

    with _auth_context("regular-user", ["rag-team"], is_admin_val=False, is_rag_admin_val=False), \
         patch("repository.lambda_functions.vs_repo") as mvs, \
         patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "coll-1"}
        mcs.update_collection.return_value = mock_coll

        from repository.lambda_functions import update_collection
        update_collection(event, ctx)

        call_kwargs = mcs.update_collection.call_args[1]
        assert call_kwargs["is_admin"] is False


# --- Pipeline update: RAG Admin scoped ---


def test_rag_admin_can_update_pipelines_on_accessible_repo(mock_auth, ctx):
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    new_pipelines = [
        {"collectionId": "coll-1", "s3Bucket": "bucket", "s3Prefix": "prefix", "trigger": "event",
         "chunkSize": 1000, "chunkOverlap": 100},
    ]
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"pipelines": new_pipelines})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mvs.update.return_value = {**ACCESSIBLE_REPO, "pipelines": new_pipelines}

        from repository.lambda_functions import update_repository
        result = update_repository(event, ctx)

    assert result["statusCode"] == 200


def test_rag_admin_cannot_update_allowed_groups(mock_auth, ctx):
    """RAG Admin cannot change allowedGroups — field restriction enforced."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"allowedGroups": ["new-group"]})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}

        from repository.lambda_functions import update_repository
        result = update_repository(event, ctx)

    assert result["statusCode"] == 403


def test_rag_admin_cannot_update_mixed_fields(mock_auth, ctx):
    """RAG Admin cannot send allowed + disallowed fields together."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"pipelines": [], "name": "sneaky-rename"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}

        from repository.lambda_functions import update_repository
        result = update_repository(event, ctx)

    assert result["statusCode"] == 403


# --- List repos: RAG Admin sees group-filtered ---


def test_rag_admin_sees_only_group_accessible_repos_in_list(mock_auth, ctx):
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs:
        mvs.get_registered_repositories.return_value = [ACCESSIBLE_REPO, INACCESSIBLE_REPO]

        from repository.lambda_functions import list_all
        result = list_all(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body) == 1
    assert body[0]["repositoryId"] == "repo-1"


# --- Document ownership: RAG Admin bypass ---


def test_rag_admin_can_delete_any_doc_in_accessible_repo(mock_auth):
    """RAG Admin can delete another user's document (ownership bypass)."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])

    doc = MagicMock()
    doc.username = "other-user"
    doc.document_id = "doc-1"

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True):
        from repository.lambda_functions import _ensure_document_ownership
        # Should NOT raise
        _ensure_document_ownership(event, [doc])


def test_regular_user_cannot_delete_other_users_doc(mock_auth):
    """Regular user cannot delete another user's document."""
    mock_auth.set_user(username="regular-user", groups=["rag-team"], is_admin=False, is_rag_admin=False)
    event = _make_event("regular-user", ["rag-team"])

    doc = MagicMock()
    doc.username = "other-user"
    doc.document_id = "doc-1"

    with _auth_context("regular-user", ["rag-team"]):
        from repository.lambda_functions import _ensure_document_ownership
        with pytest.raises(ValueError, match="not owned by"):
            _ensure_document_ownership(event, [doc])


# --- Regression: Admin unchanged ---


def test_admin_can_create_collection(mock_auth, ctx):
    mock_auth.set_user(username="admin-user", groups=["admin"], is_admin=True, is_rag_admin=False)
    event = _make_event("admin-user", ["admin"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"name": "New Collection", "embeddingModel": "model-1"})

    with _auth_context("admin-user", ["admin"], is_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs, \
         patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "new-coll", "name": "New Collection"}
        mcs.create_collection.return_value = mock_coll

        from repository.lambda_functions import create_collection
        result = create_collection(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["collectionId"] == "new-coll"


def test_admin_can_update_all_repo_fields(mock_auth, ctx):
    """Admin can update allowedGroups and other fields (not restricted like RAG admin)."""
    mock_auth.set_user(username="admin-user", groups=["admin"], is_admin=True, is_rag_admin=False)
    event = _make_event("admin-user", ["admin"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"allowedGroups": ["new-group"], "pipelines": []})

    with _auth_context("admin-user", ["admin"], is_admin_val=True), \
         patch("repository.lambda_functions.vs_repo") as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mvs.update.return_value = {**ACCESSIBLE_REPO, "allowedGroups": ["new-group"]}

        from repository.lambda_functions import update_repository
        result = update_repository(event, ctx)

    assert result["statusCode"] == 200
