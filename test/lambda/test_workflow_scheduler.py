import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

os.environ["AWS_REGION"] = "us-east-1"
os.environ["MODEL_TABLE_NAME"] = "model-table"
os.environ["GUARDRAILS_TABLE_NAME"] = "guardrails-table"
os.environ["WORKFLOW_ORCHESTRATION_TABLE_NAME"] = "workflow-orchestration-table"


def test_create_schedule_calls_put_rule_and_put_targets():
    with patch("workflow_orchestration.scheduler.events_client") as mock_events:
        from workflow_orchestration.scheduler import create_schedule

        with patch.dict(os.environ, {"WORKFLOW_SCHEDULER_TARGET_ARN": "arn:aws:lambda:us-east-1:123456789012:function:workflow-step"}, clear=False):
            create_schedule("wf-123", "cron(0 12 * * ? *)")

        mock_events.put_rule.assert_called_once_with(
            Name="lisa-workflow-wf-123",
            ScheduleExpression="cron(0 12 * * ? *)",
            State="ENABLED",
            Description="Scheduled run for workflow wf-123",
        )
        mock_events.put_targets.assert_called_once_with(
            Rule="lisa-workflow-wf-123",
            Targets=[
                {
                    "Id": "workflow-wf-123",
                    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:workflow-step",
                    "Input": '{"workflowId": "wf-123"}',
                }
            ],
        )


def test_create_schedule_passes_custom_payload_input():
    with patch("workflow_orchestration.scheduler.events_client") as mock_events:
        from workflow_orchestration.scheduler import create_schedule

        with patch.dict(os.environ, {"WORKFLOW_SCHEDULER_TARGET_ARN": "arn:aws:lambda:us-east-1:123456789012:function:workflow-step"}, clear=False):
            create_schedule(
                "wf-123",
                "cron(0 12 * * ? *)",
                payload={"workflowId": "wf-123", "steps": [{"stepId": "s1"}], "context": {"workflowId": "wf-123"}},
            )

        mock_events.put_targets.assert_called_once_with(
            Rule="lisa-workflow-wf-123",
            Targets=[
                {
                    "Id": "workflow-wf-123",
                    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:workflow-step",
                    "Input": '{"workflowId": "wf-123", "steps": [{"stepId": "s1"}], "context": {"workflowId": "wf-123"}}',
                }
            ],
        )


def test_create_schedule_includes_role_arn_for_step_functions_target():
    with patch("workflow_orchestration.scheduler.events_client") as mock_events:
        from workflow_orchestration.scheduler import create_schedule

        with patch.dict(
            os.environ,
            {
                "WORKFLOW_SCHEDULER_TARGET_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:workflow-step",
                "WORKFLOW_SCHEDULER_TARGET_ROLE_ARN": "arn:aws:iam::123456789012:role/workflow-target-invoke-role",
            },
            clear=False,
        ):
            create_schedule("wf-123", "cron(0 12 * * ? *)")

        mock_events.put_targets.assert_called_once_with(
            Rule="lisa-workflow-wf-123",
            Targets=[
                {
                    "Id": "workflow-wf-123",
                    "Arn": "arn:aws:states:us-east-1:123456789012:stateMachine:workflow-step",
                    "RoleArn": "arn:aws:iam::123456789012:role/workflow-target-invoke-role",
                    "Input": '{"workflowId": "wf-123"}',
                }
            ],
        )


def test_create_schedule_raises_when_step_functions_target_role_arn_missing():
    with patch("workflow_orchestration.scheduler.events_client"):
        from workflow_orchestration.scheduler import create_schedule

        with patch.dict(
            os.environ,
            {
                "WORKFLOW_SCHEDULER_TARGET_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:workflow-step",
                "WORKFLOW_SCHEDULER_TARGET_ROLE_ARN": "",
            },
            clear=False,
        ):
            with pytest.raises(
                ValueError,
                match="WORKFLOW_SCHEDULER_TARGET_ROLE_ARN is required when WORKFLOW_SCHEDULER_TARGET_ARN is a Step Functions state machine",
            ):
                create_schedule("wf-123", "cron(0 12 * * ? *)")


def test_create_schedule_uses_configured_rule_prefix():
    with patch("workflow_orchestration.scheduler.events_client") as mock_events:
        from workflow_orchestration.scheduler import create_schedule

        with patch.dict(
            os.environ,
            {
                "WORKFLOW_SCHEDULER_TARGET_ARN": "arn:aws:lambda:us-east-1:123456789012:function:workflow-step",
                "WORKFLOW_SCHEDULE_RULE_PREFIX": "test-lisa-workflow",
            },
            clear=False,
        ):
            create_schedule("wf-123", "cron(0 12 * * ? *)")

        mock_events.put_rule.assert_called_once_with(
            Name="test-lisa-workflow-wf-123",
            ScheduleExpression="cron(0 12 * * ? *)",
            State="ENABLED",
            Description="Scheduled run for workflow wf-123",
        )
        mock_events.put_targets.assert_called_once_with(
            Rule="test-lisa-workflow-wf-123",
            Targets=[
                {
                    "Id": "workflow-wf-123",
                    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:workflow-step",
                    "Input": '{"workflowId": "wf-123"}',
                }
            ],
        )


def test_create_schedule_raises_on_missing_cron_expression():
    from workflow_orchestration.scheduler import create_schedule

    with pytest.raises(ValueError, match="schedule is required"):
        create_schedule("wf-123", "")


def test_create_schedule_raises_when_target_arn_missing():
    with patch("workflow_orchestration.scheduler.events_client"):
        from workflow_orchestration.scheduler import create_schedule

        with patch.dict(os.environ, {"WORKFLOW_SCHEDULER_TARGET_ARN": ""}, clear=False):
            with pytest.raises(ValueError, match="WORKFLOW_SCHEDULER_TARGET_ARN is required"):
                create_schedule("wf-123", "cron(0 12 * * ? *)")


def test_delete_schedule_calls_remove_targets_and_delete_rule():
    with patch("workflow_orchestration.scheduler.events_client") as mock_events:
        from workflow_orchestration.scheduler import delete_schedule

        delete_schedule("wf-123")

        mock_events.remove_targets.assert_called_once_with(
            Rule="lisa-workflow-wf-123",
            Ids=["workflow-wf-123"],
        )
        mock_events.delete_rule.assert_called_once_with(Name="lisa-workflow-wf-123", Force=True)
