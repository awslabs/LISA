"""EventBridge schedule helpers for workflow orchestration."""

from __future__ import annotations

import logging
import os
import json

import boto3
from utilities.common_functions import retry_config

logger = logging.getLogger(__name__)

events_client = boto3.client("events", region_name=os.environ["AWS_REGION"], config=retry_config)


def _schedule_rule_name(workflow_id: str) -> str:
    prefix = str(os.environ.get("WORKFLOW_SCHEDULE_RULE_PREFIX") or "lisa-workflow").strip()
    if not prefix:
        prefix = "lisa-workflow"
    return f"{prefix}-{workflow_id}"


def _normalize_cron_expression(cron_expression: str | None) -> str:
    value = str(cron_expression or "").strip()
    if not value:
        raise ValueError("schedule is required and must be a non-empty cron expression")
    if not (value.startswith("cron(") or value.startswith("rate(")):
        raise ValueError("schedule must be a valid EventBridge cron/rate expression")
    return value


def _target_arn() -> str:
    value = str(os.environ.get("WORKFLOW_SCHEDULER_TARGET_ARN") or "").strip()
    if not value:
        raise ValueError(
            "WORKFLOW_SCHEDULER_TARGET_ARN is required when schedule is configured"
        )
    return value


def _target_role_arn() -> str:
    return str(os.environ.get("WORKFLOW_SCHEDULER_TARGET_ROLE_ARN") or "").strip()


def _is_step_functions_state_machine_arn(target_arn: str) -> bool:
    return ":states:" in target_arn and ":stateMachine:" in target_arn


def _put_schedule_target(workflow_id: str, rule_name: str, payload: dict | None = None) -> None:
    target_arn = _target_arn()
    target_role_arn = _target_role_arn()
    if _is_step_functions_state_machine_arn(target_arn) and not target_role_arn:
        raise ValueError(
            "WORKFLOW_SCHEDULER_TARGET_ROLE_ARN is required when WORKFLOW_SCHEDULER_TARGET_ARN is a Step Functions state machine"
        )

    target = {
        "Id": f"workflow-{workflow_id}",
        "Arn": target_arn,
        "Input": json.dumps(payload if payload is not None else {"workflowId": workflow_id}),
    }
    if target_role_arn:
        target["RoleArn"] = target_role_arn

    events_client.put_targets(
        Rule=rule_name,
        Targets=[target],
    )


def _remove_schedule_target(workflow_id: str, rule_name: str) -> None:
    events_client.remove_targets(
        Rule=rule_name,
        Ids=[f"workflow-{workflow_id}"],
    )


def create_schedule(workflow_id: str, cron_expression: str | None, payload: dict | None = None) -> None:
    expression = _normalize_cron_expression(cron_expression)
    rule_name = _schedule_rule_name(workflow_id)
    events_client.put_rule(
        Name=rule_name,
        ScheduleExpression=expression,
        State="ENABLED",
        Description=f"Scheduled run for workflow {workflow_id}",
    )
    _put_schedule_target(workflow_id, rule_name, payload)


def delete_schedule(workflow_id: str) -> None:
    rule_name = _schedule_rule_name(workflow_id)
    _remove_schedule_target(workflow_id, rule_name)
    events_client.delete_rule(Name=rule_name, Force=True)
