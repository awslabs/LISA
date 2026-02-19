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

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["CHAT_ASSISTANT_STACKS_TABLE_NAME"] = "chat-assistant-stacks-table"
os.environ["ADMIN_GROUP"] = "admin-group"

retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_api_wrapper(func):
    """Wrap result in HTTP response; on exception return error response."""

    def wrapper(event, context):
        try:
            result = func(event, context)
            return {
                "statusCode": 200,
                "body": json.dumps(result, default=str),
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
            }
        except Exception as e:
            if hasattr(e, "http_status_code"):
                status_code = e.http_status_code
                error_message = getattr(e, "message", str(e))
            elif isinstance(e, ValueError):
                error_message = str(e)
                status_code = 400
                if "not found" in error_message.lower():
                    status_code = 404
            else:
                status_code = 400
                error_message = str(e)
            return {
                "statusCode": status_code,
                "body": json.dumps({"error": error_message}, default=str),
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
            }

    return wrapper


@pytest.fixture(scope="module")
def chat_stacks_handlers():
    """Patch retry_config and api_wrapper only for this module, then import handlers. No global mocks."""
    with patch("utilities.common_functions.retry_config", retry_config), patch(
        "utilities.common_functions.api_wrapper", mock_api_wrapper
    ):
        from chat_assistant_stacks.lambda_functions import (
            create,
            delete,
            get_stack,
            list_stacks,
            update,
            update_status,
        )

        yield SimpleNamespace(
            create=create,
            delete=delete,
            get_stack=get_stack,
            list_stacks=list_stacks,
            update=update,
            update_status=update_status,
        )


@pytest.fixture(autouse=True)
def patch_is_admin_for_chat_stacks():
    """Patch is_admin in lambda_functions and utilities.auth. True by default; 403 tests set False."""
    mock_is_admin = MagicMock(return_value=True)
    with (
        patch("chat_assistant_stacks.lambda_functions.is_admin", mock_is_admin),
        patch("utilities.auth.is_admin", mock_is_admin),
    ):
        yield mock_is_admin


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def stacks_table(dynamodb):
    """Create a mock DynamoDB table for chat assistant stacks."""
    table = dynamodb.create_table(
        TableName="chat-assistant-stacks-table",
        KeySchema=[{"AttributeName": "stackId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "stackId", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    with patch("chat_assistant_stacks.lambda_functions.table", table):
        yield table


@pytest.fixture
def admin_event():
    """Event with admin user (is_admin patched True by patch_is_admin_for_chat_stacks)."""
    return {"requestContext": {"authorizer": {"username": "admin-user"}}}


def _non_admin_event(groups=None):
    """Event for non-admin user; groups is list, stored as JSON string in authorizer."""
    if groups is None:
        groups = []
    import json as _json

    return {
        "requestContext": {
            "authorizer": {
                "username": "normal-user",
                "groups": _json.dumps(groups),
            }
        },
    }


@pytest.fixture
def sample_stack_body():
    """Minimal valid stack body for create."""
    return {
        "name": "Test Stack",
        "description": "A test assistant stack",
        "modelIds": ["model-1"],
        "repositoryIds": [],
        "collectionIds": [],
        "mcpServerIds": [],
        "mcpToolIds": [],
        "directivePromptIds": [],
        "allowedGroups": [],
    }


def test_list_stacks_empty(stacks_table, lambda_context, admin_event, chat_stacks_handlers):
    """Test listing stacks when table is empty."""
    h = chat_stacks_handlers
    response = h.list_stacks(admin_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["Items"] == []


def test_create_stack(stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers):
    """Test creating a new stack."""
    h = chat_stacks_handlers
    event = {**admin_event, "body": json.dumps(sample_stack_body)}
    response = h.create(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "Test Stack"
    assert body["description"] == "A test assistant stack"
    assert body["modelIds"] == ["model-1"]
    assert "stackId" in body
    assert body["isActive"] is True
    assert "created" in body
    assert "updated" in body


def test_list_stacks_after_create(stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers):
    """Test listing stacks returns created stack."""
    h = chat_stacks_handlers
    event = {**admin_event, "body": json.dumps(sample_stack_body)}
    h.create(event, lambda_context)
    response = h.list_stacks(admin_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["Items"]) == 1
    assert body["Items"][0]["name"] == "Test Stack"


def test_get_stack(stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers):
    """Test getting a stack by id."""
    h = chat_stacks_handlers
    create_event = {**admin_event, "body": json.dumps(sample_stack_body)}
    create_resp = h.create(create_event, lambda_context)
    stack_id = json.loads(create_resp["body"])["stackId"]
    get_event = {**admin_event, "pathParameters": {"stackId": stack_id}}
    response = h.get_stack(get_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["stackId"] == stack_id
    assert body["name"] == "Test Stack"


def test_get_stack_not_found(stacks_table, lambda_context, admin_event, chat_stacks_handlers):
    """Test get_stack returns 404 for missing stack."""
    h = chat_stacks_handlers
    event = {**admin_event, "pathParameters": {"stackId": "nonexistent-id"}}
    response = h.get_stack(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in body.get("error", "").lower()


def test_update_stack(stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers):
    """Test updating a stack."""
    h = chat_stacks_handlers
    create_event = {**admin_event, "body": json.dumps(sample_stack_body)}
    create_resp = h.create(create_event, lambda_context)
    stack_id = json.loads(create_resp["body"])["stackId"]
    update_body = {**sample_stack_body, "name": "Updated Stack", "description": "Updated description"}
    update_event = {
        **admin_event,
        "pathParameters": {"stackId": stack_id},
        "body": json.dumps(update_body),
    }
    response = h.update(update_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "Updated Stack"
    assert body["description"] == "Updated description"
    assert body["stackId"] == stack_id


def test_update_stack_not_found(stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers):
    """Test update returns 404 for missing stack."""
    h = chat_stacks_handlers
    update_body = {**sample_stack_body, "name": "Updated"}
    event = {
        **admin_event,
        "pathParameters": {"stackId": "nonexistent-id"},
        "body": json.dumps(update_body),
    }
    response = h.update(event, lambda_context)
    assert response["statusCode"] == 404


def test_delete_stack(stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers):
    """Test deleting a stack."""
    h = chat_stacks_handlers
    create_event = {**admin_event, "body": json.dumps(sample_stack_body)}
    create_resp = h.create(create_event, lambda_context)
    stack_id = json.loads(create_resp["body"])["stackId"]
    delete_event = {**admin_event, "pathParameters": {"stackId": stack_id}}
    response = h.delete(delete_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body.get("status") == "ok"
    # Verify gone
    get_event = {**admin_event, "pathParameters": {"stackId": stack_id}}
    get_resp = h.get_stack(get_event, lambda_context)
    assert get_resp["statusCode"] == 404


def test_delete_stack_not_found(stacks_table, lambda_context, admin_event, chat_stacks_handlers):
    """Test delete returns 404 for missing stack."""
    h = chat_stacks_handlers
    event = {**admin_event, "pathParameters": {"stackId": "nonexistent-id"}}
    response = h.delete(event, lambda_context)
    assert response["statusCode"] == 404


def test_update_status(stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers):
    """Test update_status toggles isActive."""
    h = chat_stacks_handlers
    create_event = {**admin_event, "body": json.dumps(sample_stack_body)}
    create_resp = h.create(create_event, lambda_context)
    stack_id = json.loads(create_resp["body"])["stackId"]
    # Deactivate
    event = {
        **admin_event,
        "pathParameters": {"stackId": stack_id},
        "body": json.dumps({"isActive": False}),
    }
    response = h.update_status(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["isActive"] is False
    # Activate again
    event["body"] = json.dumps({"isActive": True})
    response2 = h.update_status(event, lambda_context)
    assert response2["statusCode"] == 200
    body2 = json.loads(response2["body"])
    assert body2["isActive"] is True


def test_update_status_not_found(stacks_table, lambda_context, admin_event, chat_stacks_handlers):
    """Test update_status returns 404 for missing stack."""
    h = chat_stacks_handlers
    event = {
        **admin_event,
        "pathParameters": {"stackId": "nonexistent-id"},
        "body": json.dumps({"isActive": False}),
    }
    response = h.update_status(event, lambda_context)
    assert response["statusCode"] == 404


def test_update_status_missing_is_active(
    stacks_table, lambda_context, admin_event, sample_stack_body, chat_stacks_handlers
):
    """Test update_status returns 400 when isActive missing."""
    h = chat_stacks_handlers
    create_event = {**admin_event, "body": json.dumps(sample_stack_body)}
    create_resp = h.create(create_event, lambda_context)
    stack_id = json.loads(create_resp["body"])["stackId"]
    event = {
        **admin_event,
        "pathParameters": {"stackId": stack_id},
        "body": json.dumps({}),
    }
    response = h.update_status(event, lambda_context)
    assert response["statusCode"] == 400


def _put_stack_item(table, stack_id, name, is_active=True, allowed_groups=None):
    """Insert a stack directly into the table (for testing non-admin filtering)."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    item = {
        "stackId": stack_id,
        "name": name,
        "description": "",
        "modelIds": [],
        "repositoryIds": [],
        "collectionIds": [],
        "mcpServerIds": [],
        "mcpToolIds": [],
        "directivePromptIds": [],
        "isActive": is_active,
        "created": now,
        "updated": now,
    }
    if allowed_groups is not None:
        item["allowedGroups"] = list(allowed_groups)
    table.put_item(Item=item)


def test_list_stacks_non_admin_empty_table_returns_200(
    stacks_table, lambda_context, patch_is_admin_for_chat_stacks, chat_stacks_handlers
):
    """Test list_stacks as non-admin returns 200 with empty list when no stacks."""
    h = chat_stacks_handlers
    patch_is_admin_for_chat_stacks.return_value = False
    event = _non_admin_event(groups=["team-a"])
    response = h.list_stacks(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["Items"] == []


def test_list_stacks_non_admin_sees_only_active_and_accessible(
    stacks_table, lambda_context, patch_is_admin_for_chat_stacks, chat_stacks_handlers
):
    """Non-admin sees active stacks with allowedGroups empty or user in group; inactive or wrong-group excluded."""
    h = chat_stacks_handlers
    _put_stack_item(stacks_table, "global-1", "Global Stack", is_active=True, allowed_groups=[])
    _put_stack_item(stacks_table, "team-a-1", "Team A Stack", is_active=True, allowed_groups=["team-a"])
    _put_stack_item(stacks_table, "team-b-1", "Team B Stack", is_active=True, allowed_groups=["team-b"])
    _put_stack_item(stacks_table, "inactive-global", "Inactive Global", is_active=False, allowed_groups=[])

    patch_is_admin_for_chat_stacks.return_value = False
    event = _non_admin_event(groups=["team-a"])
    response = h.list_stacks(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    items = body["Items"]
    assert len(items) == 2
    names = {i["name"] for i in items}
    assert "Global Stack" in names
    assert "Team A Stack" in names
    assert "Team B Stack" not in names
    assert "Inactive Global" not in names


def test_list_stacks_non_admin_no_groups_sees_only_global(
    stacks_table, lambda_context, patch_is_admin_for_chat_stacks, chat_stacks_handlers
):
    """Non-admin with no groups sees only stacks that have empty allowedGroups."""
    h = chat_stacks_handlers
    _put_stack_item(stacks_table, "global-1", "Global", is_active=True, allowed_groups=[])
    _put_stack_item(stacks_table, "restricted-1", "Restricted", is_active=True, allowed_groups=["some-group"])

    patch_is_admin_for_chat_stacks.return_value = False
    event = _non_admin_event(groups=[])
    response = h.list_stacks(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    items = body["Items"]
    assert len(items) == 1
    assert items[0]["name"] == "Global"


def test_list_stacks_admin_sees_all_including_inactive_and_restricted(
    stacks_table, lambda_context, admin_event, chat_stacks_handlers
):
    """Admin list_stacks returns all stacks including inactive and any allowedGroups."""
    h = chat_stacks_handlers
    _put_stack_item(stacks_table, "global-1", "Global", is_active=True, allowed_groups=[])
    _put_stack_item(stacks_table, "inactive-1", "Inactive", is_active=False, allowed_groups=[])
    _put_stack_item(stacks_table, "restricted-1", "Restricted", is_active=True, allowed_groups=["other"])

    response = h.list_stacks(admin_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    items = body["Items"]
    assert len(items) == 3
    names = {i["name"] for i in items}
    assert "Global" in names
    assert "Inactive" in names
    assert "Restricted" in names


def test_create_forbidden_when_not_admin(
    stacks_table, lambda_context, patch_is_admin_for_chat_stacks, sample_stack_body, chat_stacks_handlers
):
    """Test create returns 403 when user is not admin."""
    h = chat_stacks_handlers
    patch_is_admin_for_chat_stacks.return_value = False
    event = {
        "requestContext": {"authorizer": {"username": "user"}},
        "body": json.dumps(sample_stack_body),
    }
    response = h.create(event, lambda_context)
    assert response["statusCode"] == 403


def test_get_stack_forbidden_when_not_admin(
    stacks_table, lambda_context, patch_is_admin_for_chat_stacks, admin_event, sample_stack_body, chat_stacks_handlers
):
    """Test get_stack returns 403 when user is not admin."""
    h = chat_stacks_handlers
    create_event = {**admin_event, "body": json.dumps(sample_stack_body)}
    create_resp = h.create(create_event, lambda_context)
    assert create_resp["statusCode"] == 200
    stack_id = json.loads(create_resp["body"])["stackId"]
    patch_is_admin_for_chat_stacks.return_value = False
    get_event = {
        "requestContext": {"authorizer": {"username": "user"}},
        "pathParameters": {"stackId": stack_id},
    }
    response = h.get_stack(get_event, lambda_context)
    assert response["statusCode"] == 403
