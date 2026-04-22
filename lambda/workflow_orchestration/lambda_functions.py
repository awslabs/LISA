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

"""Lambda functions for managing workflow definitions in DynamoDB."""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from typing import Any, cast

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from utilities.auth import admin_only, get_groups, is_admin, user_has_group_access
from utilities.common_functions import api_wrapper, retry_config
from utilities.exceptions import ConflictException, NotFoundException
from utilities.time import iso_string

from .execution_engine import execute_step, summarize_step_results
from .models import WorkflowDefinition
from .scheduler import create_schedule, delete_schedule

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["WORKFLOW_ORCHESTRATION_TABLE_NAME"])
WORKFLOW_DEFINITION_RECORD_TYPE = "WORKFLOW_DEFINITION"
WORKFLOW_TEMPLATE_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "nightly-rag-summary": [
        {
            "stepId": "collect-context",
            "name": "Collect RAG context",
            "type": "tool",
            "config": {"tool": "rag_context_collector"},
        },
        {
            "stepId": "generate-summary",
            "name": "Generate summary",
            "type": "llm",
            "config": {"promptTemplate": "nightly-rag-summary"},
        },
    ],
}


def _get_workflow_id(event: dict) -> str:
    params = event.get("pathParameters") or {}
    workflow_id = params.get("workflowId")
    if not workflow_id:
        raise ValueError("workflowId is required")
    return str(workflow_id)


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(item, default=str)))


def _extract_schedule_value(payload: dict[str, Any]) -> str | None:
    if "schedule" not in payload:
        return None
    schedule = str(payload.get("schedule") or "").strip()
    if not schedule:
        raise ValueError("schedule is required and must be a non-empty cron expression")
    return schedule


def _is_workflow_definition(item: dict[str, Any]) -> bool:
    return item.get("recordType") == WORKFLOW_DEFINITION_RECORD_TYPE


def _materialize_template_steps(payload: dict[str, Any]) -> dict[str, Any]:
    template_id_raw = payload.get("templateId")
    template_id = str(template_id_raw).strip() if template_id_raw is not None else ""
    if not template_id:
        return payload

    steps = payload.get("steps")
    if isinstance(steps, list) and len(steps) > 0:
        return payload

    template_steps = WORKFLOW_TEMPLATE_REGISTRY.get(template_id)
    if template_steps is None:
        raise ValueError(f"Unsupported workflow templateId '{template_id}'")

    payload["templateId"] = template_id
    payload["steps"] = [dict(step) for step in template_steps]
    return payload


def _schedule_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflowId": item["workflowId"],
        "steps": item.get("steps", []),
        "context": {"workflowId": item["workflowId"]},
    }


def _can_user_access_workflow(event: dict, workflow: dict[str, Any]) -> bool:
    if is_admin(event):
        return True
    if not workflow.get("status") == "ACTIVE":
        return False
    allowed_groups = workflow.get("allowedGroups", [])
    if not allowed_groups:
        return True
    return user_has_group_access(get_groups(event), allowed_groups)


@api_wrapper
def list_workflows(event: dict, context: dict) -> dict:
    try:
        response = table.scan(FilterExpression=Attr("recordType").eq(WORKFLOW_DEFINITION_RECORD_TYPE))
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = table.scan(
                FilterExpression=Attr("recordType").eq(WORKFLOW_DEFINITION_RECORD_TYPE),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        if is_admin(event):
            return {"Items": [_serialize_item(workflow) for workflow in items]}

        filtered = [workflow for workflow in items if _can_user_access_workflow(event, workflow)]
        return {"Items": [_serialize_item(workflow) for workflow in filtered]}
    except ClientError:
        logger.exception("Error listing workflows")
        raise


@api_wrapper
def get_workflow(event: dict, context: dict) -> dict:
    workflow_id = _get_workflow_id(event)
    try:
        response = table.get_item(Key={"workflowId": workflow_id})
        item = response.get("Item")
        if not item or not _is_workflow_definition(item) or not _can_user_access_workflow(event, item):
            raise NotFoundException(f"Workflow {workflow_id} not found.")
        return _serialize_item(item)
    except ClientError:
        logger.exception("Error getting workflow %s", workflow_id)
        raise


@api_wrapper
@admin_only
def create(event: dict, context: dict) -> dict:
    body = json.loads(event["body"], parse_float=Decimal)
    body = _materialize_template_steps(body)
    schedule = _extract_schedule_value(body)
    body.pop("workflowId", None)
    model = WorkflowDefinition(**body)
    item = model.model_dump(exclude_none=True)
    if schedule:
        item["schedule"] = schedule
    item["recordType"] = WORKFLOW_DEFINITION_RECORD_TYPE
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(workflowId)")
        if schedule:
            try:
                create_schedule(item["workflowId"], schedule, _schedule_payload(item))
            except Exception:
                table.delete_item(Key={"workflowId": item["workflowId"]})
                raise
        return _serialize_item(item)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ConflictException(f"Workflow {item['workflowId']} already exists.") from exc
        logger.exception("Error creating workflow")
        raise


@api_wrapper
@admin_only
def update(event: dict, context: dict) -> dict:
    workflow_id = _get_workflow_id(event)
    body = json.loads(event["body"], parse_float=Decimal)
    body = _materialize_template_steps(body)
    schedule = _extract_schedule_value(body)
    body["workflowId"] = workflow_id
    model = WorkflowDefinition(**body)
    try:
        response = table.get_item(Key={"workflowId": workflow_id})
        if not response.get("Item"):
            raise NotFoundException(f"Workflow {workflow_id} not found.")
        existing = response["Item"]
        item = model.model_dump(exclude_none=True)
        item["recordType"] = WORKFLOW_DEFINITION_RECORD_TYPE
        item["created"] = existing.get("created", item.get("created"))
        item["updated"] = iso_string()
        previous_schedule = existing.get("schedule")
        if schedule:
            item["schedule"] = schedule
        table.put_item(Item=item)
        try:
            if schedule:
                create_schedule(workflow_id, schedule, _schedule_payload(item))
            elif previous_schedule:
                delete_schedule(workflow_id)
        except Exception:
            table.put_item(Item=existing)
            raise
        return _serialize_item(item)
    except ClientError:
        logger.exception("Error updating workflow %s", workflow_id)
        raise


@api_wrapper
@admin_only
def delete(event: dict, context: dict) -> dict:
    workflow_id = _get_workflow_id(event)
    try:
        response = table.delete_item(Key={"workflowId": workflow_id}, ReturnValues="ALL_OLD")
        if not response.get("Attributes"):
            raise NotFoundException(f"Workflow {workflow_id} not found.")
        if response["Attributes"].get("schedule"):
            delete_schedule(workflow_id)
        return {"status": "ok"}
    except ClientError:
        logger.exception("Error deleting workflow %s", workflow_id)
        raise


@api_wrapper
def execute_workflow_step(event: dict, context: dict) -> dict:
    """Execute one workflow step via the local execution engine."""
    payload: dict[str, Any]
    body = event.get("body")
    if isinstance(body, str):
        payload = cast(dict[str, Any], json.loads(body or "{}"))
    elif isinstance(body, dict):
        payload = body
    else:
        payload = cast(dict[str, Any], event)

    mode = str(payload.get("mode", "")).strip().lower()
    if mode == "summarize_results":
        return summarize_step_results(cast(list[dict[str, Any]], payload.get("stepResults") or []))

    step = payload.get("step") or {}
    execution_context = payload.get("context") or {}
    return execute_step(step, execution_context)


@api_wrapper
@admin_only
def approve_workflow_step(event: dict, context: dict) -> dict:
    """Record an approval action and move a run back to RUNNING."""
    body = event.get("body")
    payload: dict[str, Any]
    if isinstance(body, str):
        payload = cast(dict[str, Any], json.loads(body or "{}"))
    elif isinstance(body, dict):
        payload = body
    else:
        payload = {}

    run_id = str(payload.get("runId", "")).strip()
    approval_token = str(payload.get("approvalToken", "")).strip()
    if not run_id:
        raise ValueError("runId is required")
    if not approval_token:
        raise ValueError("approvalToken is required")

    run_key = f"run::{run_id}"
    response = table.get_item(Key={"workflowId": run_key})
    existing = response.get("Item")
    if not existing:
        raise NotFoundException(f"Workflow run {run_id} not found.")
    now = iso_string()
    try:
        table.update_item(
            Key={"workflowId": run_key},
            UpdateExpression=(
                "SET #state = :running, "
                "#updated = :updated, "
                "#recordType = if_not_exists(#recordType, :recordType), "
                "#runId = if_not_exists(#runId, :runId), "
                "#approval.#approvalToken = :approvalToken, "
                "#approval.#approvedAt = :approvedAt"
            ),
            ConditionExpression=(
                "#state = :waitingApproval "
                "AND ((attribute_exists(#approval) AND #approval.#approvalToken = :approvalToken) "
                "OR #approvalToken = :approvalToken)"
            ),
            ExpressionAttributeNames={
                "#state": "state",
                "#updated": "updated",
                "#recordType": "recordType",
                "#runId": "runId",
                "#approval": "approval",
                "#approvalToken": "approvalToken",
                "#approvedAt": "approvedAt",
            },
            ExpressionAttributeValues={
                ":running": "RUNNING",
                ":waitingApproval": "WAITING_APPROVAL",
                ":updated": now,
                ":recordType": "WORKFLOW_RUN_STATE",
                ":runId": run_id,
                ":approvalToken": approval_token,
                ":approvedAt": now,
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ConflictException(
                f"Workflow run {run_id} is not waiting for this approval token."
            ) from exc
        logger.exception("Error approving workflow run %s", run_id)
        raise
    return {"runId": run_id, "state": "RUNNING"}
