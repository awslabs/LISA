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
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["MODEL_TABLE_NAME"] = "model-table"
os.environ["GUARDRAILS_TABLE_NAME"] = "guardrails-table"
os.environ["WORKFLOW_ORCHESTRATION_TABLE_NAME"] = "workflow-orchestration-table"
os.environ["ADMIN_GROUP"] = "admin-group"
os.environ["WORKFLOW_SCHEDULER_TARGET_ARN"] = "arn:aws:lambda:us-east-1:123456789012:function:workflow-step"

retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_api_wrapper(func):
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
                status_code = 400
                error_message = str(e)
            else:
                status_code = 400
                error_message = str(e)
            return {
                "statusCode": status_code,
                "body": json.dumps({"error": error_message}, default=str),
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
            }

    return wrapper


@pytest.fixture(autouse=True)
def patch_is_admin_for_workflows():
    mock_is_admin = MagicMock(return_value=True)
    with (
        patch("workflow_orchestration.lambda_functions.is_admin", mock_is_admin),
        patch("utilities.auth.is_admin", mock_is_admin),
    ):
        yield mock_is_admin


@pytest.fixture(scope="function")
def workflow_handlers(patch_is_admin_for_workflows):
    for mod in list(sys.modules.keys()):
        if mod == "workflow_orchestration" or mod.startswith("workflow_orchestration."):
            del sys.modules[mod]
    with patch("utilities.common_functions.retry_config", retry_config), patch(
        "utilities.common_functions.api_wrapper", mock_api_wrapper
    ):
        from workflow_orchestration.lambda_functions import (
            approve_workflow_step,
            create,
            delete,
            execute_workflow_step,
            get_workflow,
            list_workflows,
            update,
        )

        yield SimpleNamespace(
            create=create,
            list=list_workflows,
            get=get_workflow,
            update=update,
            delete=delete,
            execute_workflow_step=execute_workflow_step,
            approve_workflow_step=approve_workflow_step,
        )


@pytest.fixture(scope="function")
def dynamodb():
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def workflows_table(dynamodb):
    table = dynamodb.create_table(
        TableName="workflow-orchestration-table",
        KeySchema=[{"AttributeName": "workflowId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "workflowId", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    with patch("workflow_orchestration.lambda_functions.table", table):
        yield table


@pytest.fixture
def lambda_context():
    return SimpleNamespace(function_name="test_function")


@pytest.fixture
def admin_event():
    return {
        "httpMethod": "POST",
        "requestContext": {"authorizer": {"username": "admin-user", "groups": '["admin-group"]'}},
    }


@pytest.fixture
def sample_workflow_body():
    return {
        "name": "Test Workflow",
        "description": "A workflow for tests",
        "steps": [{"stepId": "step-1", "name": "Call tool", "type": "tool"}],
        "status": "ACTIVE",
    }


def test_create_workflow(workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers):
    h = workflow_handlers
    event = {**admin_event, "body": json.dumps(sample_workflow_body)}
    response = h.create(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "Test Workflow"
    assert body["status"] == "ACTIVE"
    assert body["steps"][0]["type"] == "tool"
    assert "workflowId" in body


def test_create_workflow_creates_schedule_when_provided(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    event = {
        **admin_event,
        "body": json.dumps({**sample_workflow_body, "schedule": "cron(0 10 * * ? *)"}),
    }
    with patch("workflow_orchestration.lambda_functions.create_schedule") as mock_create_schedule:
        response = h.create(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    mock_create_schedule.assert_called_once_with(
        body["workflowId"],
        "cron(0 10 * * ? *)",
        {
            "workflowId": body["workflowId"],
            "steps": body["steps"],
            "context": {"workflowId": body["workflowId"]},
        },
    )


def test_create_workflow_materializes_template_steps_when_steps_missing(
    workflows_table, lambda_context, admin_event, workflow_handlers
):
    h = workflow_handlers
    event = {
        **admin_event,
        "body": json.dumps(
            {
                "name": "Nightly Summary",
                "description": "Uses template",
                "templateId": "nightly-rag-summary",
                "steps": [],
                "status": "ACTIVE",
            }
        ),
    }

    response = h.create(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["templateId"] == "nightly-rag-summary"
    assert len(body["steps"]) > 0
    assert body["steps"][0]["type"] == "tool"


def test_create_workflow_rejects_blank_schedule(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    event = {
        **admin_event,
        "body": json.dumps({**sample_workflow_body, "schedule": "   "}),
    }

    response = h.create(event, lambda_context)

    assert response["statusCode"] == 400
    assert "schedule is required" in json.loads(response["body"])["error"]


def test_create_workflow_rolls_back_when_schedule_creation_fails(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    event = {
        **admin_event,
        "body": json.dumps({**sample_workflow_body, "schedule": "cron(0 10 * * ? *)"}),
    }
    with patch(
        "workflow_orchestration.lambda_functions.create_schedule",
        side_effect=RuntimeError("schedule failed"),
    ):
        response = h.create(event, lambda_context)

    assert response["statusCode"] == 400
    assert "schedule failed" in json.loads(response["body"])["error"]
    items = workflows_table.scan().get("Items", [])
    assert items == []


def test_create_workflow_forbidden_when_not_admin(
    workflows_table, lambda_context, patch_is_admin_for_workflows, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    patch_is_admin_for_workflows.return_value = False
    event = {
        "httpMethod": "POST",
        "requestContext": {"authorizer": {"username": "normal-user", "groups": "[]"}},
        "body": json.dumps(sample_workflow_body),
    }
    response = h.create(event, lambda_context)
    assert response["statusCode"] == 403


def test_create_workflow_ignores_client_workflow_id(workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers):
    h = workflow_handlers
    event_body = {**sample_workflow_body, "workflowId": "client-controlled-id"}
    event = {**admin_event, "body": json.dumps(event_body)}

    response = h.create(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["workflowId"] != "client-controlled-id"
    stored = workflows_table.get_item(Key={"workflowId": "client-controlled-id"}).get("Item")
    assert stored is None


def test_create_workflow_returns_conflict_on_duplicate(workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers):
    h = workflow_handlers
    first_response = h.create({**admin_event, "body": json.dumps(sample_workflow_body)}, lambda_context)
    first_body = json.loads(first_response["body"])
    duplicate_body = {**sample_workflow_body, "workflowId": first_body["workflowId"]}

    duplicate_response = h.create({**admin_event, "body": json.dumps(duplicate_body)}, lambda_context)

    assert duplicate_response["statusCode"] == 200
    duplicate_body_response = json.loads(duplicate_response["body"])
    assert duplicate_body_response["workflowId"] != first_body["workflowId"]

    with patch("workflow_orchestration.lambda_functions.WorkflowDefinition") as mock_model:
        forced_item = {
            "workflowId": first_body["workflowId"],
            "name": sample_workflow_body["name"],
            "description": sample_workflow_body["description"],
            "steps": sample_workflow_body["steps"],
            "status": sample_workflow_body["status"],
            "allowedGroups": [],
        }
        mock_model.return_value.model_dump.return_value = forced_item
        forced_response = h.create({**admin_event, "body": json.dumps(sample_workflow_body)}, lambda_context)
        assert forced_response["statusCode"] == 409
        assert "already exists" in json.loads(forced_response["body"])["error"]


def test_list_workflows_filters_for_non_admin_active_and_group_access(
    workflows_table, lambda_context, patch_is_admin_for_workflows, workflow_handlers
):
    h = workflow_handlers
    patch_is_admin_for_workflows.return_value = False
    workflows_table.put_item(
        Item={
            "workflowId": "wf-active-group-access",
            "recordType": "WORKFLOW_DEFINITION",
            "name": "Visible",
            "description": "visible",
            "steps": [],
            "status": "ACTIVE",
            "allowedGroups": ["group-a"],
        }
    )
    workflows_table.put_item(
        Item={
            "workflowId": "wf-active-no-access",
            "recordType": "WORKFLOW_DEFINITION",
            "name": "Hidden No Group",
            "description": "hidden",
            "steps": [],
            "status": "ACTIVE",
            "allowedGroups": ["group-b"],
        }
    )
    workflows_table.put_item(
        Item={
            "workflowId": "wf-paused-group-access",
            "recordType": "WORKFLOW_DEFINITION",
            "name": "Hidden Paused",
            "description": "hidden",
            "steps": [],
            "status": "PAUSED",
            "allowedGroups": ["group-a"],
        }
    )
    workflows_table.put_item(
        Item={
            "workflowId": "wf-active-public",
            "recordType": "WORKFLOW_DEFINITION",
            "name": "Visible Public",
            "description": "visible",
            "steps": [],
            "status": "ACTIVE",
            "allowedGroups": [],
        }
    )
    event = {
        "httpMethod": "GET",
        "requestContext": {"authorizer": {"username": "normal-user", "groups": '["group-a"]'}},
    }

    with patch("workflow_orchestration.lambda_functions.get_groups", return_value=["group-a"]):
        response = h.list(event, lambda_context)

    assert response["statusCode"] == 200
    items = json.loads(response["body"])["Items"]
    workflow_ids = {item["workflowId"] for item in items}
    assert workflow_ids == {"wf-active-group-access", "wf-active-public"}


def test_list_workflows_excludes_non_definition_records(workflows_table, lambda_context, workflow_handlers):
    h = workflow_handlers
    workflows_table.put_item(
        Item={
            "workflowId": "wf-definition",
            "recordType": "WORKFLOW_DEFINITION",
            "name": "Definition Workflow",
            "description": "visible",
            "steps": [],
            "status": "ACTIVE",
            "allowedGroups": [],
        }
    )
    workflows_table.put_item(
        Item={
            "workflowId": "run::run-123",
            "recordType": "WORKFLOW_RUN_STATE",
            "runId": "run-123",
            "state": "RUNNING",
        }
    )

    response = h.list({"httpMethod": "GET"}, lambda_context)

    assert response["statusCode"] == 200
    items = json.loads(response["body"])["Items"]
    workflow_ids = {item["workflowId"] for item in items}
    assert workflow_ids == {"wf-definition"}


def test_get_workflow_behaviors(workflows_table, lambda_context, patch_is_admin_for_workflows, workflow_handlers):
    h = workflow_handlers
    patch_is_admin_for_workflows.return_value = False
    workflows_table.put_item(
        Item={
            "workflowId": "wf-get",
            "recordType": "WORKFLOW_DEFINITION",
            "name": "Get Workflow",
            "description": "visible",
            "steps": [],
            "status": "ACTIVE",
            "allowedGroups": ["group-a"],
        }
    )
    ok_event = {
        "httpMethod": "GET",
        "pathParameters": {"workflowId": "wf-get"},
        "requestContext": {"authorizer": {"username": "normal-user", "groups": '["group-a"]'}},
    }

    with patch("workflow_orchestration.lambda_functions.get_groups", return_value=["group-a"]):
        ok_response = h.get(ok_event, lambda_context)
    assert ok_response["statusCode"] == 200
    assert json.loads(ok_response["body"])["workflowId"] == "wf-get"

    missing_id_response = h.get({"httpMethod": "GET", "pathParameters": {}}, lambda_context)
    assert missing_id_response["statusCode"] == 400
    assert "workflowId is required" in json.loads(missing_id_response["body"])["error"]

    not_found_event = {
        "httpMethod": "GET",
        "pathParameters": {"workflowId": "does-not-exist"},
        "requestContext": {"authorizer": {"username": "normal-user", "groups": '["group-a"]'}},
    }
    with patch("workflow_orchestration.lambda_functions.get_groups", return_value=["group-a"]):
        not_found_response = h.get(not_found_event, lambda_context)
    assert not_found_response["statusCode"] == 404


def test_get_workflow_rejects_non_definition_record(workflows_table, lambda_context, workflow_handlers):
    h = workflow_handlers
    workflows_table.put_item(
        Item={
            "workflowId": "run::run-123",
            "recordType": "WORKFLOW_RUN_STATE",
            "runId": "run-123",
            "state": "RUNNING",
        }
    )

    response = h.get({"httpMethod": "GET", "pathParameters": {"workflowId": "run::run-123"}}, lambda_context)
    assert response["statusCode"] == 404
    assert "run::run-123" in json.loads(response["body"])["error"]


def test_update_workflow_behaviors(workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers):
    h = workflow_handlers
    create_response = h.create({**admin_event, "body": json.dumps(sample_workflow_body)}, lambda_context)
    workflow_id = json.loads(create_response["body"])["workflowId"]
    update_event = {
        **admin_event,
        "httpMethod": "PUT",
        "pathParameters": {"workflowId": workflow_id},
        "body": json.dumps({**sample_workflow_body, "name": "Updated Workflow"}),
    }

    update_response = h.update(update_event, lambda_context)
    assert update_response["statusCode"] == 200
    assert json.loads(update_response["body"])["name"] == "Updated Workflow"

    missing_id_response = h.update({**admin_event, "httpMethod": "PUT", "pathParameters": {}, "body": json.dumps(sample_workflow_body)}, lambda_context)
    assert missing_id_response["statusCode"] == 400
    assert "workflowId is required" in json.loads(missing_id_response["body"])["error"]

    not_found_response = h.update(
        {
            **admin_event,
            "httpMethod": "PUT",
            "pathParameters": {"workflowId": "does-not-exist"},
            "body": json.dumps(sample_workflow_body),
        },
        lambda_context,
    )
    assert not_found_response["statusCode"] == 404


def test_update_workflow_upserts_schedule(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    create_response = h.create({**admin_event, "body": json.dumps(sample_workflow_body)}, lambda_context)
    workflow_id = json.loads(create_response["body"])["workflowId"]
    update_event = {
        **admin_event,
        "httpMethod": "PUT",
        "pathParameters": {"workflowId": workflow_id},
        "body": json.dumps({**sample_workflow_body, "schedule": "cron(0 11 * * ? *)"}),
    }

    with patch("workflow_orchestration.lambda_functions.create_schedule") as mock_create_schedule:
        update_response = h.update(update_event, lambda_context)

    assert update_response["statusCode"] == 200
    body = json.loads(update_response["body"])
    mock_create_schedule.assert_called_once_with(
        workflow_id,
        "cron(0 11 * * ? *)",
        {
            "workflowId": workflow_id,
            "steps": body["steps"],
            "context": {"workflowId": workflow_id},
        },
    )


def test_update_workflow_materializes_template_steps_when_steps_missing(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    create_response = h.create({**admin_event, "body": json.dumps(sample_workflow_body)}, lambda_context)
    workflow_id = json.loads(create_response["body"])["workflowId"]
    update_event = {
        **admin_event,
        "httpMethod": "PUT",
        "pathParameters": {"workflowId": workflow_id},
        "body": json.dumps(
            {
                "name": "Template Update",
                "description": "Template-based update",
                "templateId": "nightly-rag-summary",
                "steps": [],
                "status": "ACTIVE",
            }
        ),
    }

    update_response = h.update(update_event, lambda_context)
    assert update_response["statusCode"] == 200
    body = json.loads(update_response["body"])
    assert body["templateId"] == "nightly-rag-summary"
    assert len(body["steps"]) > 0


def test_update_workflow_deletes_existing_schedule_when_removed(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    create_response = h.create(
        {**admin_event, "body": json.dumps({**sample_workflow_body, "schedule": "cron(0 9 * * ? *)"})},
        lambda_context,
    )
    workflow_id = json.loads(create_response["body"])["workflowId"]
    update_event = {
        **admin_event,
        "httpMethod": "PUT",
        "pathParameters": {"workflowId": workflow_id},
        "body": json.dumps({**sample_workflow_body}),
    }

    with patch("workflow_orchestration.lambda_functions.delete_schedule") as mock_delete_schedule:
        update_response = h.update(update_event, lambda_context)

    assert update_response["statusCode"] == 200
    mock_delete_schedule.assert_called_once_with(workflow_id)


def test_update_workflow_rolls_back_when_schedule_upsert_fails(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    create_response = h.create(
        {**admin_event, "body": json.dumps({**sample_workflow_body, "schedule": "cron(0 9 * * ? *)"})},
        lambda_context,
    )
    workflow_id = json.loads(create_response["body"])["workflowId"]
    update_event = {
        **admin_event,
        "httpMethod": "PUT",
        "pathParameters": {"workflowId": workflow_id},
        "body": json.dumps({**sample_workflow_body, "name": "Should Not Persist", "schedule": "cron(0 11 * * ? *)"}),
    }

    with patch(
        "workflow_orchestration.lambda_functions.create_schedule",
        side_effect=RuntimeError("schedule failed"),
    ):
        update_response = h.update(update_event, lambda_context)

    assert update_response["statusCode"] == 400
    assert "schedule failed" in json.loads(update_response["body"])["error"]
    persisted = workflows_table.get_item(Key={"workflowId": workflow_id}).get("Item")
    assert persisted is not None
    assert persisted["name"] == sample_workflow_body["name"]
    assert persisted["schedule"] == "cron(0 9 * * ? *)"


def test_delete_workflow_behaviors(workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers):
    h = workflow_handlers
    create_response = h.create({**admin_event, "body": json.dumps(sample_workflow_body)}, lambda_context)
    workflow_id = json.loads(create_response["body"])["workflowId"]

    delete_response = h.delete({**admin_event, "httpMethod": "DELETE", "pathParameters": {"workflowId": workflow_id}}, lambda_context)
    assert delete_response["statusCode"] == 200
    assert json.loads(delete_response["body"])["status"] == "ok"

    missing_id_response = h.delete({**admin_event, "httpMethod": "DELETE", "pathParameters": {}}, lambda_context)
    assert missing_id_response["statusCode"] == 400
    assert "workflowId is required" in json.loads(missing_id_response["body"])["error"]

    not_found_response = h.delete(
        {**admin_event, "httpMethod": "DELETE", "pathParameters": {"workflowId": "does-not-exist"}},
        lambda_context,
    )
    assert not_found_response["statusCode"] == 404


def test_delete_workflow_removes_schedule_when_present(
    workflows_table, lambda_context, admin_event, sample_workflow_body, workflow_handlers
):
    h = workflow_handlers
    create_response = h.create(
        {**admin_event, "body": json.dumps({**sample_workflow_body, "schedule": "cron(0 7 * * ? *)"})},
        lambda_context,
    )
    workflow_id = json.loads(create_response["body"])["workflowId"]

    with patch("workflow_orchestration.lambda_functions.delete_schedule") as mock_delete_schedule:
        delete_response = h.delete(
            {**admin_event, "httpMethod": "DELETE", "pathParameters": {"workflowId": workflow_id}},
            lambda_context,
        )

    assert delete_response["statusCode"] == 200
    mock_delete_schedule.assert_called_once_with(workflow_id)


def test_execute_workflow_step_supports_api_gateway_payload(lambda_context, workflow_handlers):
    h = workflow_handlers
    event = {
        "body": json.dumps(
            {
                "step": {"stepId": "s1", "type": "tool"},
                "context": {"workflowId": "wf-1"},
            }
        )
    }

    with patch("workflow_orchestration.lambda_functions.execute_step", return_value={"status": "SUCCEEDED"}) as mock_execute:
        response = h.execute_workflow_step(event, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "SUCCEEDED"
    mock_execute.assert_called_once_with({"stepId": "s1", "type": "tool"}, {"workflowId": "wf-1"})


def test_execute_workflow_step_supports_direct_step_functions_payload(lambda_context, workflow_handlers):
    h = workflow_handlers
    event = {
        "step": {"stepId": "s2", "type": "approval"},
        "context": {"workflowId": "wf-2", "executionId": "exec-2"},
    }

    with patch(
        "workflow_orchestration.lambda_functions.execute_step", return_value={"status": "WAITING_APPROVAL"}
    ) as mock_execute:
        response = h.execute_workflow_step(event, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "WAITING_APPROVAL"
    mock_execute.assert_called_once_with(
        {"stepId": "s2", "type": "approval"},
        {"workflowId": "wf-2", "executionId": "exec-2"},
    )


def test_execute_workflow_step_supports_summary_mode(lambda_context, workflow_handlers):
    h = workflow_handlers
    event = {
        "mode": "summarize_results",
        "stepResults": [
            {"stepId": "s1", "status": "SUCCEEDED"},
            {"stepId": "s2", "status": "FAILED"},
        ],
    }

    with patch(
        "workflow_orchestration.lambda_functions.summarize_step_results",
        return_value={"status": "PARTIAL", "stepResults": event["stepResults"]},
    ) as mock_summarize:
        response = h.execute_workflow_step(event, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "PARTIAL"
    mock_summarize.assert_called_once_with(event["stepResults"])


def test_approve_workflow_step_resumes_run(workflows_table, lambda_context, admin_event, workflow_handlers):
    h = workflow_handlers
    workflows_table.put_item(
        Item={
            "workflowId": "run::run-123",
            "recordType": "WORKFLOW_RUN_STATE",
            "runId": "run-123",
            "state": "WAITING_APPROVAL",
            "approval": {"approvalToken": "approval::token-123"},
        }
    )
    event = {
        **admin_event,
        "httpMethod": "POST",
        "body": json.dumps({"runId": "run-123", "approvalToken": "approval::token-123"}),
    }

    response = h.approve_workflow_step(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body == {"runId": "run-123", "state": "RUNNING"}

    stored = workflows_table.get_item(Key={"workflowId": "run::run-123"}).get("Item")
    assert stored is not None
    assert stored["state"] == "RUNNING"
    assert stored["approval"]["approvalToken"] == "approval::token-123"
    assert "approvedAt" in stored["approval"]


def test_approve_workflow_step_returns_not_found_when_run_missing(workflows_table, lambda_context, admin_event, workflow_handlers):
    h = workflow_handlers
    event = {
        **admin_event,
        "httpMethod": "POST",
        "body": json.dumps({"runId": "run-missing", "approvalToken": "approval::token-123"}),
    }

    response = h.approve_workflow_step(event, lambda_context)
    assert response["statusCode"] == 404
    assert "run-missing" in json.loads(response["body"])["error"]


def test_approve_workflow_step_returns_conflict_when_run_not_waiting(workflows_table, lambda_context, admin_event, workflow_handlers):
    h = workflow_handlers
    workflows_table.put_item(
        Item={
            "workflowId": "run::run-123",
            "recordType": "WORKFLOW_RUN_STATE",
            "runId": "run-123",
            "state": "RUNNING",
            "approval": {"approvalToken": "approval::token-123"},
        }
    )

    response = h.approve_workflow_step(
        {**admin_event, "body": json.dumps({"runId": "run-123", "approvalToken": "approval::token-123"})},
        lambda_context,
    )
    assert response["statusCode"] == 409
    assert "not waiting for this approval token" in json.loads(response["body"])["error"]


def test_approve_workflow_step_returns_conflict_when_token_mismatch(workflows_table, lambda_context, admin_event, workflow_handlers):
    h = workflow_handlers
    workflows_table.put_item(
        Item={
            "workflowId": "run::run-123",
            "recordType": "WORKFLOW_RUN_STATE",
            "runId": "run-123",
            "state": "WAITING_APPROVAL",
            "approval": {"approvalToken": "approval::expected-token"},
        }
    )

    response = h.approve_workflow_step(
        {**admin_event, "body": json.dumps({"runId": "run-123", "approvalToken": "approval::wrong-token"})},
        lambda_context,
    )
    assert response["statusCode"] == 409
    assert "not waiting for this approval token" in json.loads(response["body"])["error"]


def test_approve_workflow_step_returns_conflict_on_second_attempt(workflows_table, lambda_context, admin_event, workflow_handlers):
    h = workflow_handlers
    workflows_table.put_item(
        Item={
            "workflowId": "run::run-123",
            "recordType": "WORKFLOW_RUN_STATE",
            "runId": "run-123",
            "state": "WAITING_APPROVAL",
            "approval": {"approvalToken": "approval::token-123"},
        }
    )
    event = {**admin_event, "body": json.dumps({"runId": "run-123", "approvalToken": "approval::token-123"})}

    first_response = h.approve_workflow_step(event, lambda_context)
    second_response = h.approve_workflow_step(event, lambda_context)

    assert first_response["statusCode"] == 200
    assert second_response["statusCode"] == 409
    assert "not waiting for this approval token" in json.loads(second_response["body"])["error"]


def test_approve_workflow_step_requires_run_id_and_token(workflows_table, lambda_context, admin_event, workflow_handlers):
    h = workflow_handlers

    response = h.approve_workflow_step({**admin_event, "body": json.dumps({"runId": "run-123"})}, lambda_context)
    assert response["statusCode"] == 400
    assert "approvalToken is required" in json.loads(response["body"])["error"]

    response = h.approve_workflow_step(
        {**admin_event, "body": json.dumps({"approvalToken": "approval::token-123"})}, lambda_context
    )
    assert response["statusCode"] == 400
    assert "runId is required" in json.loads(response["body"])["error"]


def test_approve_workflow_step_forbidden_when_not_admin(
    workflows_table, lambda_context, patch_is_admin_for_workflows, workflow_handlers
):
    h = workflow_handlers
    patch_is_admin_for_workflows.return_value = False
    event = {
        "httpMethod": "POST",
        "requestContext": {"authorizer": {"username": "normal-user", "groups": "[]"}},
        "body": json.dumps({"runId": "run-123", "approvalToken": "approval::token-123"}),
    }

    response = h.approve_workflow_step(event, lambda_context)
    assert response["statusCode"] == 403


def test_docs_reference_workflow_feature_flags():
    docs_text = Path("lib/docs/config/configuration-ui.md").read_text(encoding="utf-8")
    assert "workflowOrchestrationEnabled" in docs_text
    assert "workflowApprovalRequiredByDefault" in docs_text
    assert "workflowScheduleEnabled" in docs_text
