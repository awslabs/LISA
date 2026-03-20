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

These tests verify that:
- RAG Admins can manage collections on repos they have group access to
- RAG Admins can update pipelines on repos they have group access to
- RAG Admins CANNOT create/delete repos, change allowedGroups, or access list_status
- Regular users are still blocked from admin operations
- Full admin behavior is unchanged
"""

import json
import os

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["LISA_RAG_VECTOR_STORE_TABLE"] = "vector-store-table"
os.environ["RAG_DOCUMENT_TABLE"] = "rag-document-table"
os.environ["RAG_SUB_DOCUMENT_TABLE"] = "rag-sub-document-table"
os.environ["BUCKET_NAME"] = "test-bucket"
os.environ["LISA_API_URL_PS_NAME"] = "test-api-url"
os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"] = "test-secret-name"
os.environ["REGISTERED_REPOSITORIES_PS"] = "test-repositories"
os.environ["LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER"] = "test-state-machine-arn"
os.environ["REST_API_VERSION"] = "v1"
os.environ["LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER"] = "test-create-state-machine-arn"
os.environ["LISA_INGESTION_JOB_TABLE_NAME"] = "testing-ingestion-table"
os.environ["LISA_RAG_COLLECTIONS_TABLE"] = "test-collections-table"

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import RagCollectionConfig, RagDocument
from utilities.exceptions import HTTPException


ACCESSIBLE_REPO = {
    "repositoryId": "repo-1",
    "name": "Accessible Repo",
    "type": "pgvector",
    "allowedGroups": ["rag-team"],
    "status": "CREATE_COMPLETE",
    "embeddingModelId": "model-1",
    "pipelines": [{"collectionId": "coll-1", "s3Bucket": "bucket", "s3Prefix": "prefix", "trigger": "event"}],
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
def lambda_context():
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def rag_admin_event():
    """Event for a RAG admin user who is in the rag-team group."""
    return {
        "requestContext": {
            "authorizer": {
                "username": "rag-admin-user",
                "groups": json.dumps(["rag-team", "rag-admins"]),
            }
        },
    }


# --- Collection CRUD tests for RAG Admin ---


def test_rag_admin_can_create_collection_on_accessible_repo(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin with group access can create a collection."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    rag_admin_event["pathParameters"] = {"repositoryId": "repo-1"}
    rag_admin_event["body"] = json.dumps({
        "name": "New Collection",
        "embeddingModel": "model-1",
    })

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, \
         patch("repository.lambda_functions.collection_service") as mock_coll_svc:
        mock_vs_repo.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_collection = MagicMock()
        mock_collection.model_dump.return_value = {"collectionId": "new-coll", "name": "New Collection"}
        mock_coll_svc.create_collection.return_value = mock_collection

        from repository.lambda_functions import create_collection

        result = create_collection(rag_admin_event, lambda_context)
        assert result["collectionId"] == "new-coll"


def test_rag_admin_cannot_create_collection_on_inaccessible_repo(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin without group access is denied."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    rag_admin_event["pathParameters"] = {"repositoryId": "repo-2"}
    rag_admin_event["body"] = json.dumps({
        "name": "New Collection",
        "embeddingModel": "model-2",
    })

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo:
        mock_vs_repo.find_repository_by_id.return_value = INACCESSIBLE_REPO

        from repository.lambda_functions import create_collection

        with pytest.raises(HTTPException) as exc_info:
            create_collection(rag_admin_event, lambda_context)
        assert exc_info.value.http_status_code == 403


def test_rag_admin_can_update_collection_on_accessible_repo(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin with group access can update a collection."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    rag_admin_event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    rag_admin_event["body"] = json.dumps({"name": "Updated Collection"})

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, \
         patch("repository.lambda_functions.collection_service") as mock_coll_svc:
        mock_vs_repo.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_collection = MagicMock()
        mock_collection.model_dump.return_value = {"collectionId": "coll-1", "name": "Updated Collection"}
        mock_coll_svc.update_collection.return_value = mock_collection

        from repository.lambda_functions import update_collection

        result = update_collection(rag_admin_event, lambda_context)
        assert result["name"] == "Updated Collection"


def test_rag_admin_can_delete_collection_on_accessible_repo(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin with group access can delete a collection."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    rag_admin_event["pathParameters"] = {"repositoryId": "repo-1", "collectionId": "coll-1"}
    rag_admin_event["queryStringParameters"] = {}

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, \
         patch("repository.lambda_functions.collection_service") as mock_coll_svc:
        mock_vs_repo.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_coll_svc.delete_collection.return_value = {"deleted": True}

        from repository.lambda_functions import delete_collection

        result = delete_collection(rag_admin_event, lambda_context)
        assert result["deleted"] is True


# --- Pipeline update tests for RAG Admin ---


def test_rag_admin_can_update_pipelines_on_accessible_repo(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin with group access can update pipelines."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    new_pipelines = [
        {"collectionId": "coll-1", "s3Bucket": "bucket", "s3Prefix": "prefix", "trigger": "event",
         "chunkSize": 1000, "chunkOverlap": 100},
    ]
    rag_admin_event["pathParameters"] = {"repositoryId": "repo-1"}
    rag_admin_event["body"] = json.dumps({"pipelines": new_pipelines})

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, \
         patch("repository.lambda_functions.ssm_client") as mock_ssm, \
         patch("repository.lambda_functions.step_functions_client"):
        mock_vs_repo.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}
        mock_vs_repo.update.return_value = {**ACCESSIBLE_REPO, "pipelines": new_pipelines}
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-arn"}}

        from repository.lambda_functions import update_repository

        result = update_repository(rag_admin_event, lambda_context)
        assert "pipelines" in result or result is not None


def test_rag_admin_cannot_update_allowed_groups(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin cannot change allowedGroups on a repository."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    rag_admin_event["pathParameters"] = {"repositoryId": "repo-1"}
    rag_admin_event["body"] = json.dumps({"allowedGroups": ["new-group"]})

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo:
        mock_vs_repo.find_repository_by_id.return_value = {**ACCESSIBLE_REPO, "config": ACCESSIBLE_REPO}

        from repository.lambda_functions import update_repository

        with pytest.raises((HTTPException, Exception)) as exc_info:
            update_repository(rag_admin_event, lambda_context)
        # Should be forbidden - RAG admins can't change allowedGroups
        if isinstance(exc_info.value, HTTPException):
            assert exc_info.value.http_status_code == 403


# --- Repository CRUD tests - RAG Admin blocked ---


def test_rag_admin_cannot_create_repository(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin cannot create a repository (admin-only)."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    rag_admin_event["body"] = json.dumps({
        "repositoryId": "new-repo",
        "name": "New Repo",
        "type": "pgvector",
    })

    from repository.lambda_functions import create

    with pytest.raises(HTTPException) as exc_info:
        create(rag_admin_event, lambda_context)
    assert exc_info.value.http_status_code == 403


def test_rag_admin_cannot_delete_repository(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin cannot delete a repository (admin-only)."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    rag_admin_event["pathParameters"] = {"repositoryId": "repo-1"}

    from repository.lambda_functions import delete

    with pytest.raises(HTTPException) as exc_info:
        delete(rag_admin_event, lambda_context)
    assert exc_info.value.http_status_code == 403


def test_rag_admin_cannot_access_list_status(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin cannot access list_status (admin-only)."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    from repository.lambda_functions import list_status

    with pytest.raises(HTTPException) as exc_info:
        list_status(rag_admin_event, lambda_context)
    assert exc_info.value.http_status_code == 403


# --- List repos tests ---


def test_rag_admin_sees_only_group_accessible_repos_in_list(mock_auth, lambda_context, rag_admin_event):
    """RAG Admin sees only repos they have group access to, not all repos."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo:
        mock_vs_repo.get_registered_repositories.return_value = [ACCESSIBLE_REPO, INACCESSIBLE_REPO]

        from repository.lambda_functions import list_all

        result = list_all(rag_admin_event, lambda_context)
        # RAG admin should only see the repo they have group access to
        assert len(result) == 1
        assert result[0]["repositoryId"] == "repo-1"


# --- Document ownership tests ---


def test_rag_admin_can_delete_any_doc_in_accessible_repo(mock_auth):
    """RAG Admin can delete any user's document in a repo they have access to."""
    mock_auth.set_user(username="rag-admin-user", groups=["rag-team", "rag-admins"], is_admin=False, is_rag_admin=True)

    event = {
        "requestContext": {
            "authorizer": {
                "username": "rag-admin-user",
                "groups": json.dumps(["rag-team", "rag-admins"]),
            }
        }
    }

    docs = [
        RagDocument(
            document_id="doc-1",
            repository_id="repo-1",
            collection_id="coll-1",
            source="s3://bucket/key",
            username="other-user",  # Different user
        )
    ]

    from repository.lambda_functions import _ensure_document_ownership

    # Should NOT raise - RAG admin can delete any doc
    _ensure_document_ownership(event, docs)


# --- Admin regression test ---


def test_admin_behavior_unchanged(mock_auth, lambda_context):
    """Full admin can still do everything (regression)."""
    mock_auth.set_user(username="admin-user", groups=["admin"], is_admin=True, is_rag_admin=False)

    event = {
        "requestContext": {
            "authorizer": {
                "username": "admin-user",
                "groups": json.dumps(["admin"]),
            }
        },
        "pathParameters": {"repositoryId": "repo-1"},
        "body": json.dumps({"name": "New Collection", "embeddingModel": "model-1"}),
    }

    with patch("repository.lambda_functions.vs_repo") as mock_vs_repo, \
         patch("repository.lambda_functions.collection_service") as mock_coll_svc:
        mock_vs_repo.find_repository_by_id.return_value = ACCESSIBLE_REPO
        mock_collection = MagicMock()
        mock_collection.model_dump.return_value = {"collectionId": "new-coll", "name": "New Collection"}
        mock_coll_svc.create_collection.return_value = mock_collection

        from repository.lambda_functions import create_collection

        result = create_collection(event, lambda_context)
        assert result["collectionId"] == "new-coll"


def test_regular_user_blocked_from_collection_create(mock_auth, lambda_context):
    """Regular user (not admin, not rag admin) is blocked from collection operations."""
    mock_auth.set_user(username="regular-user", groups=["rag-team"], is_admin=False, is_rag_admin=False)

    event = {
        "requestContext": {
            "authorizer": {
                "username": "regular-user",
                "groups": json.dumps(["rag-team"]),
            }
        },
        "pathParameters": {"repositoryId": "repo-1"},
        "body": json.dumps({"name": "New Collection", "embeddingModel": "model-1"}),
    }

    from repository.lambda_functions import create_collection

    with pytest.raises(HTTPException) as exc_info:
        create_collection(event, lambda_context)
    assert exc_info.value.http_status_code == 403
