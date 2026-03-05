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

"""Unit tests for the GET /project (list_projects) pathway."""
import functools
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Path setup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

# Environment variables required at import time
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ["PROJECTS_TABLE_NAME"] = "projects-table"
os.environ["SESSIONS_TABLE_NAME"] = "sessions-table"
os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"] = "byUserId"
os.environ["CONFIG_TABLE_NAME"] = "config-table"
os.environ.setdefault("GENERATED_IMAGES_S3_BUCKET_NAME", "bucket")


def _mock_api_wrapper(_func=None, **kwargs):
    from utilities.response_builder import generate_exception_response, generate_html_response

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            try:
                result = func(*args, **kw)
                if isinstance(result, dict) and "statusCode" in result:
                    return result
                return generate_html_response(200, result)
            except Exception as e:
                return generate_exception_response(e)

        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator


mock_create_env = MagicMock()
patch.dict("sys.modules", {"create_env_variables": mock_create_env}).start()
patch("utilities.common_functions.api_wrapper", _mock_api_wrapper).start()

from projects.lambda_functions import (  # noqa: E402
    _config_cache,
    _get_max_projects_per_user,
    assign_session_project,
    create_project,
    delete_project,
    list_projects,
    rename_project,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lambda_context():
    return SimpleNamespace(function_name="test", aws_request_id="req-id")


@pytest.fixture(scope="function")
def dynamodb():
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def projects_table(dynamodb):
    table = dynamodb.create_table(
        TableName="projects-table",
        KeySchema=[
            {"AttributeName": "userId", "KeyType": "HASH"},
            {"AttributeName": "projectId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "userId", "AttributeType": "S"},
            {"AttributeName": "projectId", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    with patch("projects.lambda_functions.projects_table", table):
        yield table


@pytest.fixture(scope="function")
def config_table(dynamodb):
    table = dynamodb.create_table(
        TableName="config-table",
        KeySchema=[
            {"AttributeName": "configScope", "KeyType": "HASH"},
            {"AttributeName": "versionId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "configScope", "AttributeType": "S"},
            {"AttributeName": "versionId", "AttributeType": "N"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    with patch("projects.lambda_functions.config_table", table):
        yield table


@pytest.fixture(scope="function")
def sessions_table(dynamodb):
    table = dynamodb.create_table(
        TableName="sessions-table",
        KeySchema=[
            {"AttributeName": "sessionId", "KeyType": "HASH"},
            {"AttributeName": "userId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "sessionId", "AttributeType": "S"},
            {"AttributeName": "userId", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    with patch("projects.lambda_functions.sessions_table", table):
        yield table


def _event(username="test-user"):
    return {"requestContext": {"authorizer": {"username": username}}}


# ---------------------------------------------------------------------------
# list_projects — happy path
# ---------------------------------------------------------------------------


def test_list_projects_empty(projects_table, lambda_context):
    """Returns empty list when user has no projects."""
    response = list_projects(_event(), lambda_context)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == []


def test_list_projects_returns_user_projects(projects_table, lambda_context):
    """Returns all projects belonging to the calling user."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "p1",
            "name": "Alpha",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "p2",
            "name": "Beta",
            "createTime": "2024-01-02T00:00:00",
        }
    )

    response = list_projects(_event(), lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 2
    project_ids = {p["projectId"] for p in body}
    assert project_ids == {"p1", "p2"}


def test_list_projects_sorted_by_create_time(projects_table, lambda_context):
    """Projects are returned sorted ascending by createTime."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "p2",
            "name": "Later",
            "createTime": "2024-02-01T00:00:00",
        }
    )
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "p1",
            "name": "Earlier",
            "createTime": "2024-01-01T00:00:00",
        }
    )

    response = list_projects(_event(), lambda_context)
    body = json.loads(response["body"])
    assert body[0]["projectId"] == "p1"
    assert body[1]["projectId"] == "p2"


def test_list_projects_excludes_other_users(projects_table, lambda_context):
    """Projects belonging to other users are not returned."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "mine",
            "name": "Mine",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    projects_table.put_item(
        Item={
            "userId": "other-user",
            "projectId": "theirs",
            "name": "Theirs",
            "createTime": "2024-01-01T00:00:00",
        }
    )

    response = list_projects(_event("test-user"), lambda_context)
    body = json.loads(response["body"])
    assert len(body) == 1
    assert body[0]["projectId"] == "mine"


# ---------------------------------------------------------------------------
# list_projects — soft-deleted projects filtered out
# ---------------------------------------------------------------------------


def test_list_projects_excludes_deleting_projects(projects_table, lambda_context):
    """Projects with status='deleting' are excluded from results."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "active",
            "name": "Active",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "gone",
            "name": "Gone",
            "createTime": "2024-01-01T00:00:00",
            "status": "deleting",
        }
    )

    response = list_projects(_event(), lambda_context)
    body = json.loads(response["body"])
    assert len(body) == 1
    assert body[0]["projectId"] == "active"


def test_list_projects_all_deleting_returns_empty(projects_table, lambda_context):
    """Returns empty list when all projects are soft-deleted."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "p1",
            "name": "P1",
            "createTime": "2024-01-01T00:00:00",
            "status": "deleting",
        }
    )

    response = list_projects(_event(), lambda_context)
    assert json.loads(response["body"]) == []


# ---------------------------------------------------------------------------
# list_projects — DynamoDB error handling
# ---------------------------------------------------------------------------


@patch("projects.lambda_functions.projects_table")
def test_list_projects_dynamodb_error_propagates(mock_table, lambda_context):
    """ClientError from DynamoDB is re-raised (500 from api_wrapper)."""
    from botocore.exceptions import ClientError

    mock_table.query.side_effect = ClientError({"Error": {"Code": "InternalServerError", "Message": "boom"}}, "Query")
    response = list_projects(_event(), lambda_context)
    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# _get_max_projects_per_user — config cache
# ---------------------------------------------------------------------------


def test_get_max_projects_per_user_from_config(config_table):
    """Reads maxProjectsPerUser from the config table."""
    config_table.put_item(
        Item={
            "configScope": "global",
            "versionId": 0,
            "configuration": {"maxProjectsPerUser": 5},
        }
    )
    _config_cache.clear()
    assert _get_max_projects_per_user() == 5


# ---------------------------------------------------------------------------
# create_project — happy path
# ---------------------------------------------------------------------------


def _create_event(username="test-user", body=None):
    return {
        "requestContext": {"authorizer": {"username": username}},
        "body": json.dumps(body) if body is not None else None,
    }


def test_create_project_returns_item(projects_table, config_table, lambda_context):
    """Creates a project and returns the new item with expected fields."""
    _config_cache.clear()
    response = create_project(_create_event(body={"name": "My Project"}), lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "My Project"
    assert body["userId"] == "test-user"
    assert "projectId" in body
    assert "createTime" in body
    assert "lastUpdated" in body


def test_create_project_persists_to_dynamo(projects_table, config_table, lambda_context):
    """Created project is actually stored in DynamoDB."""
    _config_cache.clear()
    response = create_project(_create_event(body={"name": "Stored"}), lambda_context)
    project_id = json.loads(response["body"])["projectId"]

    result = projects_table.get_item(Key={"userId": "test-user", "projectId": project_id})
    assert result.get("Item") is not None
    assert result["Item"]["name"] == "Stored"


# ---------------------------------------------------------------------------
# create_project — limit enforcement
# ---------------------------------------------------------------------------


def test_create_project_enforces_limit(projects_table, config_table, lambda_context):
    """Returns 400 when the user has reached maxProjectsPerUser."""
    _config_cache.clear()
    config_table.put_item(
        Item={
            "configScope": "global",
            "versionId": 1,
            "configuration": {"maxProjectsPerUser": 2},
        }
    )
    _config_cache.clear()

    for i in range(2):
        projects_table.put_item(
            Item={
                "userId": "test-user",
                "projectId": f"p{i}",
                "name": f"Project {i}",
                "createTime": "2024-01-01T00:00:00",
            }
        )

    response = create_project(_create_event(body={"name": "One Too Many"}), lambda_context)
    assert response["statusCode"] == 400
    assert "limit" in json.loads(response["body"])["error"].lower()


# ---------------------------------------------------------------------------
# create_project — input validation
# ---------------------------------------------------------------------------


def test_create_project_invalid_json_returns_400(projects_table, config_table, lambda_context):
    """Malformed JSON body returns 400."""
    _config_cache.clear()
    event = {"requestContext": {"authorizer": {"username": "test-user"}}, "body": "{not json}"}
    response = create_project(event, lambda_context)
    assert response["statusCode"] == 400


def test_create_project_empty_name_returns_400(projects_table, config_table, lambda_context):
    """Empty name fails Pydantic validation and returns 400."""
    _config_cache.clear()
    response = create_project(_create_event(body={"name": ""}), lambda_context)
    assert response["statusCode"] == 400


def test_create_project_missing_name_returns_400(projects_table, config_table, lambda_context):
    """Missing name field fails Pydantic validation and returns 400."""
    _config_cache.clear()
    response = create_project(_create_event(body={}), lambda_context)
    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# create_project — DynamoDB error handling
# ---------------------------------------------------------------------------


@patch("projects.lambda_functions.projects_table")
@patch("projects.lambda_functions._get_max_projects_per_user", return_value=10)
def test_create_project_dynamo_count_error_propagates(mock_limit, mock_table, lambda_context):
    """ClientError during count query is re-raised (400 from api_wrapper)."""
    from botocore.exceptions import ClientError

    mock_table.query.side_effect = ClientError({"Error": {"Code": "InternalServerError", "Message": "boom"}}, "Query")
    response = create_project(_create_event(body={"name": "Test"}), lambda_context)
    assert response["statusCode"] == 400


def test_get_max_projects_per_user_default(config_table):
    """Returns 10 when config table has no global entry."""
    _config_cache.clear()
    assert _get_max_projects_per_user() == 10


@patch("projects.lambda_functions.config_table")
def test_get_max_projects_per_user_error_returns_default(mock_config_table):
    """Returns 10 on any exception reading config."""
    mock_config_table.query.side_effect = Exception("db error")
    _config_cache.clear()
    assert _get_max_projects_per_user() == 10


# ---------------------------------------------------------------------------
# rename_project — helpers
# ---------------------------------------------------------------------------


def _rename_event(project_id="proj-1", username="test-user", body=None):
    return {
        "requestContext": {"authorizer": {"username": username}},
        "pathParameters": {"projectId": project_id} if project_id is not None else {},
        "body": json.dumps(body) if body is not None else None,
    }


# ---------------------------------------------------------------------------
# rename_project — happy path
# ---------------------------------------------------------------------------


def test_rename_project_success(projects_table, lambda_context):
    """Successfully renames an existing project and returns 200."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "Old Name",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    response = rename_project(_rename_event(body={"name": "New Name"}), lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Project renamed successfully"


def test_rename_project_updates_dynamo(projects_table, lambda_context):
    """The name attribute is actually updated in DynamoDB."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "Old Name",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    rename_project(_rename_event(body={"name": "Updated"}), lambda_context)
    item = projects_table.get_item(Key={"userId": "test-user", "projectId": "proj-1"})["Item"]
    assert item["name"] == "Updated"


# ---------------------------------------------------------------------------
# rename_project — input validation
# ---------------------------------------------------------------------------


def test_rename_project_missing_project_id_returns_400(projects_table, lambda_context):
    """Missing projectId path parameter returns 400."""
    event = _rename_event(project_id=None, body={"name": "X"})
    response = rename_project(event, lambda_context)
    assert response["statusCode"] == 400


def test_rename_project_invalid_json_returns_400(projects_table, lambda_context):
    """Malformed JSON body returns 400."""
    event = {
        "requestContext": {"authorizer": {"username": "test-user"}},
        "pathParameters": {"projectId": "proj-1"},
        "body": "{not json}",
    }
    response = rename_project(event, lambda_context)
    assert response["statusCode"] == 400


def test_rename_project_empty_name_returns_400(projects_table, lambda_context):
    """Empty name fails Pydantic validation and returns 400."""
    response = rename_project(_rename_event(body={"name": ""}), lambda_context)
    assert response["statusCode"] == 400


def test_rename_project_missing_name_returns_400(projects_table, lambda_context):
    """Missing name field fails Pydantic validation and returns 400."""
    response = rename_project(_rename_event(body={}), lambda_context)
    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# rename_project — not found / error handling
# ---------------------------------------------------------------------------


def test_rename_project_not_found_returns_404(projects_table, lambda_context):
    """Returns 404 when the project does not exist (ConditionalCheckFailedException)."""
    response = rename_project(_rename_event(body={"name": "Ghost"}), lambda_context)
    assert response["statusCode"] == 404
    assert "not found" in json.loads(response["body"])["error"].lower()


@patch("projects.lambda_functions.projects_table")
def test_rename_project_dynamo_error_propagates(mock_table, lambda_context):
    """Unexpected ClientError from DynamoDB is re-raised (400 from api_wrapper)."""
    from botocore.exceptions import ClientError

    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "UpdateItem"
    )
    response = rename_project(_rename_event(body={"name": "Boom"}), lambda_context)
    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# assign_session_project — helpers
# ---------------------------------------------------------------------------


def _assign_event(project_id="proj-1", session_id="sess-1", username="test-user", body=None):
    path_params = {}
    if project_id is not None:
        path_params["projectId"] = project_id
    if session_id is not None:
        path_params["sessionId"] = session_id
    return {
        "requestContext": {"authorizer": {"username": username}},
        "pathParameters": path_params,
        "body": json.dumps(body) if body is not None else None,
    }


# ---------------------------------------------------------------------------
# assign_session_project — input validation
# ---------------------------------------------------------------------------


def test_assign_session_project_missing_project_id_returns_400(sessions_table, projects_table, lambda_context):
    """Missing projectId path parameter returns 400."""
    response = assign_session_project(_assign_event(project_id=None), lambda_context)
    assert response["statusCode"] == 400


def test_assign_session_project_missing_session_id_returns_400(sessions_table, projects_table, lambda_context):
    """Missing sessionId path parameter returns 400."""
    response = assign_session_project(_assign_event(session_id=None), lambda_context)
    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# assign_session_project — ownership checks
# ---------------------------------------------------------------------------


def test_assign_session_project_session_not_found_returns_404(sessions_table, projects_table, lambda_context):
    """Returns 404 when the session does not belong to the calling user."""
    response = assign_session_project(_assign_event(), lambda_context)
    assert response["statusCode"] == 404
    assert "session" in json.loads(response["body"])["error"].lower()


def test_assign_session_project_project_not_found_returns_404(sessions_table, projects_table, lambda_context):
    """Returns 404 when the project does not belong to the calling user."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user"})
    response = assign_session_project(_assign_event(), lambda_context)
    assert response["statusCode"] == 404
    assert "project" in json.loads(response["body"])["error"].lower()


def test_assign_session_project_deleting_project_returns_409(sessions_table, projects_table, lambda_context):
    """Returns 409 when the target project is being deleted."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user"})
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "status": "deleting",
        }
    )
    response = assign_session_project(_assign_event(), lambda_context)
    assert response["statusCode"] == 409
    assert "deleted" in json.loads(response["body"])["error"].lower()


# ---------------------------------------------------------------------------
# assign_session_project — happy path (assign)
# ---------------------------------------------------------------------------


def test_assign_session_project_success(sessions_table, projects_table, lambda_context):
    """Assigns a session to a project and returns 200."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user"})
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "lastUpdated": "2024-01-01T00:00:00",
        }
    )
    response = assign_session_project(_assign_event(), lambda_context)
    assert response["statusCode"] == 200
    assert "updated" in json.loads(response["body"])["message"].lower()


def test_assign_session_project_sets_project_id_on_session(sessions_table, projects_table, lambda_context):
    """After assignment the session item has the correct projectId."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user"})
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "lastUpdated": "2024-01-01T00:00:00",
        }
    )
    assign_session_project(_assign_event(), lambda_context)
    item = sessions_table.get_item(Key={"sessionId": "sess-1", "userId": "test-user"})["Item"]
    assert item.get("projectId") == "proj-1"


def test_assign_session_project_updates_project_last_updated(sessions_table, projects_table, lambda_context):
    """After assignment the project's lastUpdated timestamp is refreshed."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user"})
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "lastUpdated": "2024-01-01T00:00:00",
        }
    )
    assign_session_project(_assign_event(), lambda_context)
    item = projects_table.get_item(Key={"userId": "test-user", "projectId": "proj-1"})["Item"]
    assert item["lastUpdated"] > "2024-01-01T00:00:00"


# ---------------------------------------------------------------------------
# assign_session_project — happy path (unassign)
# ---------------------------------------------------------------------------


def test_unassign_session_project_success(sessions_table, projects_table, lambda_context):
    """Unassigns a session from a project and returns 200."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user", "projectId": "proj-1"})
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "lastUpdated": "2024-01-01T00:00:00",
        }
    )
    response = assign_session_project(_assign_event(body={"unassign": True}), lambda_context)
    assert response["statusCode"] == 200


def test_unassign_session_project_removes_project_id(sessions_table, projects_table, lambda_context):
    """After unassign the session item no longer has a projectId."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user", "projectId": "proj-1"})
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "lastUpdated": "2024-01-01T00:00:00",
        }
    )
    assign_session_project(_assign_event(body={"unassign": True}), lambda_context)
    item = sessions_table.get_item(Key={"sessionId": "sess-1", "userId": "test-user"})["Item"]
    assert "projectId" not in item


def test_unassign_skips_project_ownership_check(sessions_table, projects_table, lambda_context):
    """Unassign bypasses the project ownership check (no 404 from that path)."""
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user", "projectId": "proj-1"})
    # No project item — ownership check is skipped; TransactWrite fails with TransactionCanceledException → 404
    response = assign_session_project(_assign_event(body={"unassign": True}), lambda_context)
    assert response["statusCode"] == 404
    assert "project" in json.loads(response["body"])["error"].lower()


# ---------------------------------------------------------------------------
# delete_project — helpers
# ---------------------------------------------------------------------------


def _delete_event(project_id="proj-1", username="test-user", body=None):
    return {
        "requestContext": {"authorizer": {"username": username}},
        "pathParameters": {"projectId": project_id} if project_id is not None else {},
        "body": json.dumps(body) if body is not None else None,
    }


# ---------------------------------------------------------------------------
# delete_project — input validation
# ---------------------------------------------------------------------------


def test_delete_project_missing_project_id_returns_400(projects_table, sessions_table, lambda_context):
    """Missing projectId path parameter returns 400."""
    response = delete_project(_delete_event(project_id=None), lambda_context)
    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# delete_project — not found
# ---------------------------------------------------------------------------


def test_delete_project_not_found_returns_404(projects_table, sessions_table, lambda_context):
    """Returns 404 when the project does not exist."""
    response = delete_project(_delete_event(), lambda_context)
    assert response["statusCode"] == 404
    assert "not found" in json.loads(response["body"])["error"].lower()


# ---------------------------------------------------------------------------
# delete_project — happy path (keep sessions)
# ---------------------------------------------------------------------------


def test_delete_project_success_returns_deleted_true(projects_table, sessions_table, lambda_context):
    """Returns 200 with deleted=True when project exists."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    with patch("projects.lambda_functions.get_all_user_sessions", return_value=[]):
        response = delete_project(_delete_event(), lambda_context)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["deleted"] is True


def test_delete_project_removes_item_from_dynamo(projects_table, sessions_table, lambda_context):
    """Project item is hard-deleted from DynamoDB."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    with patch("projects.lambda_functions.get_all_user_sessions", return_value=[]):
        delete_project(_delete_event(), lambda_context)
    result = projects_table.get_item(Key={"userId": "test-user", "projectId": "proj-1"})
    assert result.get("Item") is None


def test_delete_project_clears_project_id_from_sessions(projects_table, sessions_table, lambda_context):
    """Sessions belonging to the project have their projectId cleared (not deleted)."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    sessions_table.put_item(Item={"sessionId": "sess-1", "userId": "test-user", "projectId": "proj-1"})
    project_sessions = [{"sessionId": "sess-1", "userId": "test-user", "projectId": "proj-1"}]
    with patch("projects.lambda_functions.get_all_user_sessions", return_value=project_sessions):
        delete_project(_delete_event(body={"deleteSessions": False}), lambda_context)
    item = sessions_table.get_item(Key={"sessionId": "sess-1", "userId": "test-user"})["Item"]
    assert "projectId" not in item


def test_delete_project_ignores_sessions_from_other_projects(projects_table, sessions_table, lambda_context):
    """Sessions belonging to a different project are not modified."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    sessions_table.put_item(Item={"sessionId": "sess-other", "userId": "test-user", "projectId": "proj-other"})
    all_sessions = [{"sessionId": "sess-other", "userId": "test-user", "projectId": "proj-other"}]
    with patch("projects.lambda_functions.get_all_user_sessions", return_value=all_sessions):
        delete_project(_delete_event(body={"deleteSessions": False}), lambda_context)
    item = sessions_table.get_item(Key={"sessionId": "sess-other", "userId": "test-user"})["Item"]
    assert item.get("projectId") == "proj-other"


# ---------------------------------------------------------------------------
# delete_project — cascade delete sessions
# ---------------------------------------------------------------------------


def test_delete_project_cascade_deletes_sessions(projects_table, sessions_table, lambda_context):
    """With deleteSessions=True, delete_user_session is called for each project session."""
    projects_table.put_item(
        Item={
            "userId": "test-user",
            "projectId": "proj-1",
            "name": "P",
            "createTime": "2024-01-01T00:00:00",
        }
    )
    project_sessions = [
        {"sessionId": "sess-1", "userId": "test-user", "projectId": "proj-1"},
        {"sessionId": "sess-2", "userId": "test-user", "projectId": "proj-1"},
    ]
    with patch("projects.lambda_functions.get_all_user_sessions", return_value=project_sessions), patch(
        "projects.lambda_functions.delete_user_session"
    ) as mock_delete_session:
        delete_project(_delete_event(body={"deleteSessions": True}), lambda_context)
    assert mock_delete_session.call_count == 2


# ---------------------------------------------------------------------------
# delete_project — DynamoDB error handling
# ---------------------------------------------------------------------------


@patch("projects.lambda_functions.projects_table")
def test_delete_project_dynamo_error_propagates(mock_table, lambda_context):
    """Unexpected ClientError from DynamoDB soft-delete is re-raised."""
    from botocore.exceptions import ClientError

    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "UpdateItem"
    )
    response = delete_project(_delete_event(), lambda_context)
    assert response["statusCode"] == 400
