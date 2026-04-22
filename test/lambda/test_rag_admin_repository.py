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

Uses _auth_context() to patch auth references directly on repository.lambda_functions. This is necessary because the
module uses `from utilities.auth import ...` which creates local bindings that conftest's patches on utilities.auth do
not reach.

Note: The conftest patches decorators (admin_only, rag_admin_or_admin) as passthroughs when test_repository_lambda.py
runs first (module-level import). So these tests focus on the inner function logic: group access filtering,
effective_admin, field restrictions, and document ownership bypass.
"""

import json
from contextlib import ExitStack
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
    "pipelines": [
        {
            "collectionId": "coll-1",
            "s3Bucket": "bucket",
            "s3Prefix": "prefix",
            "trigger": "event",
            "autoRemove": True,
            "chunkSize": 1000,
            "chunkOverlap": 100,
        }
    ],
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


def _auth_context(username, groups, is_admin_val=False, is_rag_admin_val=False):
    """Patch all auth references on repository.lambda_functions for a test.

    Because repository.lambda_functions uses `from utilities.auth import ...`, the module has local bindings that must
    be patched directly.
    """
    stack = ExitStack()
    for p in [
        patch("repository.lambda_functions.get_username", return_value=username),
        patch("repository.lambda_functions.get_groups", return_value=groups),
        patch("repository.lambda_functions.is_admin", return_value=is_admin_val),
        patch("repository.lambda_functions.is_rag_admin", return_value=is_rag_admin_val),
        patch("repository.lambda_functions.get_user_context", return_value=(username, is_admin_val, groups)),
    ]:
        stack.enter_context(p)
    return stack


# --- Collection CRUD: RAG Admin with group access ---


def test_rag_admin_can_create_collection_on_accessible_repo(ctx):
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"name": "New Collection", "embeddingModel": "model-1"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs, patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "new-coll", "name": "New Collection"}
        mcs.create_collection.return_value = mock_coll

        from repository.lambda_functions import create_collection

        result = create_collection(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["collectionId"] == "new-coll"


def test_rag_admin_cannot_create_collection_on_inaccessible_repo(ctx):
    """RAG Admin without group access is denied by get_repository."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-2"}
    event["body"] = json.dumps({"name": "New Collection", "embeddingModel": "model-2"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = INACCESSIBLE_REPO

        from repository.lambda_functions import create_collection

        result = create_collection(event, ctx)

    assert result["statusCode"] == 403


def test_rag_admin_can_update_collection_on_accessible_repo(ctx):
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    event["body"] = json.dumps({"name": "Updated Collection"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs, patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "coll-1", "name": "Updated Collection"}
        mcs.update_collection.return_value = mock_coll

        from repository.lambda_functions import update_collection

        result = update_collection(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["name"] == "Updated Collection"


def test_rag_admin_can_delete_collection_on_accessible_repo(ctx):
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    event["queryStringParameters"] = {}

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs, patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mcs.delete_collection.return_value = {"deleted": True}

        from repository.lambda_functions import delete_collection

        result = delete_collection(event, ctx)

    assert result["statusCode"] == 200


# --- effective_admin: RAG Admin gets is_admin=True in collection_service ---


@pytest.mark.parametrize(
    "is_rag_admin_val,expected",
    [(True, True), (False, False)],
    ids=["rag-admin-gets-effective-admin", "regular-user-gets-no-admin"],
)
def test_effective_admin_passed_to_collection_service(ctx, is_rag_admin_val, expected):
    """Verify effective_admin (is_admin OR is_rag_admin) is passed to collection_service.

    Call-arg inspection is necessary here because collection_service is always mocked at this layer — it's an external
    dependency boundary.
    """
    username = "rag-admin-user" if is_rag_admin_val else "regular-user"
    groups = ["rag-team", "rag-admins"] if is_rag_admin_val else ["rag-team"]
    event = _make_event(username, groups)
    event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    event["body"] = json.dumps({"name": "Updated"})

    with _auth_context(username, groups, is_rag_admin_val=is_rag_admin_val), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs, patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "coll-1"}
        mcs.update_collection.return_value = mock_coll

        from repository.lambda_functions import update_collection

        update_collection(event, ctx)

        call_kwargs = mcs.update_collection.call_args[1]
        assert call_kwargs["is_admin"] is expected


# --- Pipeline update: RAG Admin scoped ---


def test_rag_admin_can_update_pipelines_on_accessible_repo(ctx):
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    new_pipelines = [
        {
            "collectionId": "coll-1",
            "s3Bucket": "bucket",
            "s3Prefix": "prefix",
            "trigger": "event",
            "chunkSize": 1000,
            "chunkOverlap": 100,
        },
    ]
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"pipelines": new_pipelines})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mvs.update.return_value = {**ACCESSIBLE_REPO, "pipelines": new_pipelines}

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == 200


def test_rag_admin_can_add_new_pipeline_to_accessible_repo(ctx):
    """RAG Admin can add a new pipeline to a repo, triggering infrastructure deployment."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    # Send existing pipeline + a new one
    new_pipeline = {
        "autoRemove": False,
        "trigger": "schedule",
        "s3Bucket": "new-bucket",
        "s3Prefix": "new-prefix",
        "collectionId": "coll-2",
        "chunkSize": 1024,
        "chunkOverlap": 102,
    }
    all_pipelines = ACCESSIBLE_REPO["pipelines"] + [new_pipeline]
    event["body"] = json.dumps({"pipelines": all_pipelines})

    updated_config = {
        **ACCESSIBLE_REPO,
        "pipelines": all_pipelines,
        "status": "UPDATE_IN_PROGRESS",
        "executionArn": "arn:execution:123",
    }

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs, patch("repository.lambda_functions.ssm_client") as mock_ssm, patch(
        "repository.lambda_functions.step_functions_client"
    ) as mock_sf:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mvs.update.return_value = updated_config
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "arn:test-state-machine"}}
        mock_sf.start_execution.return_value = {"executionArn": "arn:execution:123"}

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "executionArn" in body
    assert body["executionArn"] == "arn:execution:123"


def test_rag_admin_cannot_update_allowed_groups(ctx):
    """RAG Admin cannot change allowedGroups — field restriction enforced."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"allowedGroups": ["new-group"]})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == 403


def test_rag_admin_cannot_update_mixed_fields(ctx):
    """RAG Admin cannot send allowed + disallowed fields together."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"pipelines": [], "name": "sneaky-rename"})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == 403


# --- List repos: RAG Admin sees group-filtered ---


def test_rag_admin_sees_only_group_accessible_repos_in_list(ctx):
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.get_registered_repositories.return_value = [ACCESSIBLE_REPO, INACCESSIBLE_REPO]

        from repository.lambda_functions import list_all

        result = list_all(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body) == 1
    assert body[0]["repositoryId"] == "repo-1"


# --- Document ownership: RAG Admin bypass ---


def test_rag_admin_can_delete_any_doc_in_accessible_repo():
    """RAG Admin can delete another user's document (ownership bypass)."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])

    doc = MagicMock()
    doc.username = "other-user"
    doc.document_id = "doc-1"

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True):
        from repository.lambda_functions import _ensure_document_ownership

        _ensure_document_ownership(event, [doc])


def test_regular_user_cannot_delete_other_users_doc():
    """Regular user cannot delete another user's document."""
    event = _make_event("regular-user", ["rag-team"])

    doc = MagicMock()
    doc.username = "other-user"
    doc.document_id = "doc-1"

    with _auth_context("regular-user", ["rag-team"]):
        from repository.lambda_functions import _ensure_document_ownership

        with pytest.raises(ValueError, match="not owned by"):
            _ensure_document_ownership(event, [doc])


# --- update_repository: RAG Admin on inaccessible repo ---


@pytest.mark.parametrize(
    "body_value,expected_status",
    [
        # Missing key: default "{}" → empty update → 200
        ("__missing__", 200),
        # Explicit None: json.loads(None) raises TypeError → caught as ValidationError → 400
        (None, 400),
    ],
    ids=["missing_key", "null_body"],
)
def test_rag_admin_update_bad_body_does_not_500(ctx, body_value, expected_status):
    """Missing or null body must not cause an unhandled TypeError (was: json.loads({}) → 500)."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    if body_value == "__missing__":
        event.pop("body", None)
    else:
        event["body"] = body_value

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mvs.update.return_value = ACCESSIBLE_REPO

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == expected_status


def test_rag_admin_cannot_update_repository_on_inaccessible_repo(ctx):
    """RAG Admin without group access is denied even with allowed fields."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-2"}
    event["body"] = json.dumps({"pipelines": []})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = INACCESSIBLE_REPO

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == 403


# --- list_user_collections: RAG Admin passes is_rag_admin, not is_admin ---


def test_rag_admin_list_user_collections_passes_is_rag_admin(ctx):
    """list_user_collections passes is_rag_admin=True for RAG admin callers.

    RAG admins get scoped-admin collection access (bypass collection-level allowedGroups) within repos they have group
    access to. Repo-level filtering uses is_admin (real flag), so RAG admins do NOT see all repos — only their group-
    accessible ones. is_rag_admin is threaded through to collection filtering.
    """
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["queryStringParameters"] = {}

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.collection_service"
    ) as mcs:
        mcs.list_all_user_collections.return_value = ([], None)

        from repository.lambda_functions import list_user_collections

        list_user_collections(event, ctx)

        call_kwargs = mcs.list_all_user_collections.call_args[1]
        assert call_kwargs["is_admin"] is False, "is_admin must remain the real flag (not effective_admin)"
        assert call_kwargs["is_rag_admin"] is True, "is_rag_admin must be passed for scoped collection access"


# --- bedrockKnowledgeBaseConfig: allowed update field for RAG Admin ---


def test_rag_admin_can_update_bedrock_knowledge_base_config(ctx):
    """RAG Admin can update bedrockKnowledgeBaseConfig (in allowed_fields set)."""
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps(
        {
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": "kb-123",
                "dataSources": [{"id": "ds-1", "name": "test-source", "s3Uri": "s3://bucket/prefix"}],
            }
        }
    )

    bedrock_repo = {
        **ACCESSIBLE_REPO,
        "type": "bedrock_kb",
        "config": {**ACCESSIBLE_REPO, "type": "bedrock_kb"},
    }

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = bedrock_repo
        mvs.update.return_value = bedrock_repo

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == 200


# --- Defense-in-depth: serialized output filter for RAG Admin ---


def test_rag_admin_update_filters_serialized_output(ctx):
    """Defense-in-depth filter strips non-allowed fields from model_dump output.

    Even if Pydantic populates default values during serialization, the second filter (lines 1613-1615) ensures only
    allowed fields reach the update call.
    """
    event = _make_event("rag-admin-user", ["rag-team", "rag-admins"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    new_pipelines = [
        {
            "collectionId": "coll-1",
            "s3Bucket": "bucket",
            "s3Prefix": "prefix",
            "trigger": "event",
            "chunkSize": 1000,
            "chunkOverlap": 100,
        },
    ]
    event["body"] = json.dumps({"pipelines": new_pipelines})

    with _auth_context("rag-admin-user", ["rag-team", "rag-admins"], is_rag_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mvs.update.return_value = {**ACCESSIBLE_REPO, "pipelines": new_pipelines}

        from repository.lambda_functions import update_repository

        update_repository(event, ctx)

        # Verify the updates dict passed to vs_repo.update only contains allowed fields
        update_call_args = mvs.update.call_args
        updates_dict = (
            update_call_args[0][1] if len(update_call_args[0]) > 1 else update_call_args[1].get("updates", {})
        )
        allowed_fields = {"pipelines", "bedrockKnowledgeBaseConfig"}
        assert set(updates_dict.keys()).issubset(
            allowed_fields
        ), f"Updates contained disallowed fields: {set(updates_dict.keys()) - allowed_fields}"


# --- Regression: Admin unchanged ---


def test_admin_can_create_collection(ctx):
    event = _make_event("admin-user", ["admin"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"name": "New Collection", "embeddingModel": "model-1"})

    with _auth_context("admin-user", ["admin"], is_admin_val=True), patch(
        "repository.lambda_functions.vs_repo"
    ) as mvs, patch("repository.lambda_functions.collection_service") as mcs:
        mvs.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll = MagicMock()
        mock_coll.model_dump.return_value = {"collectionId": "new-coll", "name": "New Collection"}
        mcs.create_collection.return_value = mock_coll

        from repository.lambda_functions import create_collection

        result = create_collection(event, ctx)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["collectionId"] == "new-coll"


def test_admin_can_update_all_repo_fields(ctx):
    """Admin can update allowedGroups and other fields (not restricted like RAG admin)."""
    event = _make_event("admin-user", ["admin"])
    event["pathParameters"] = {"repositoryId": "repo-1"}
    event["body"] = json.dumps({"allowedGroups": ["new-group"], "pipelines": []})

    with _auth_context("admin-user", ["admin"], is_admin_val=True), patch("repository.lambda_functions.vs_repo") as mvs:
        mvs.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mvs.update.return_value = {**ACCESSIBLE_REPO, "allowedGroups": ["new-group"]}

        from repository.lambda_functions import update_repository

        result = update_repository(event, ctx)

    assert result["statusCode"] == 200
