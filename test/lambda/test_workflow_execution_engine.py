import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("MODEL_TABLE_NAME", "model-table")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "guardrails-table")
os.environ.setdefault("WORKFLOW_ORCHESTRATION_TABLE_NAME", "workflow-orchestration-table")
os.environ.setdefault("ADMIN_GROUP", "admin-group")

from workflow_orchestration.execution_engine import execute_step, run_agent_loop, summarize_step_results


def test_execute_step_tool_succeeds():
    step = {"stepId": "s1", "type": "tool", "name": "my-tool"}
    ctx = {"workflowId": "wf-1"}

    result = execute_step(step, ctx)

    assert result["status"] == "SUCCEEDED"
    assert result["stepId"] == "s1"
    assert result["type"] == "tool"
    assert "output" in result
    assert result["output"]["runner"] == "tool"


def test_execute_step_approval_waits():
    step = {"stepId": "s2", "type": "approval", "name": "approval gate"}
    ctx = {"workflowId": "wf-1", "executionId": "exec-123"}

    result = execute_step(step, ctx)

    assert result["status"] == "WAITING_APPROVAL"
    assert result["stepId"] == "s2"
    assert result["type"] == "approval"
    assert isinstance(result["approvalToken"], str)
    assert result["approvalToken"]


def test_execute_step_llm_succeeds():
    step = {"stepId": "s3", "type": "llm", "name": "summarize"}
    ctx = {"workflowId": "wf-1"}

    result = execute_step(step, ctx)

    assert result["status"] == "SUCCEEDED"
    assert result["stepId"] == "s3"
    assert result["type"] == "llm"
    assert "output" in result
    assert result["output"]["runner"] == "llm"


def test_execute_step_unknown_type_raises_value_error():
    step = {"stepId": "s4", "type": "not-real"}
    ctx = {"workflowId": "wf-1"}

    with pytest.raises(ValueError, match="Unknown step type"):
        execute_step(step, ctx)


def test_run_agent_loop_stops_at_max_iterations():
    plan = [{"action": "think"}, {"action": "act"}, {"action": "think"}]
    context = {"sessionId": "sess-1"}

    result = run_agent_loop(plan=plan, max_iterations=2, context=context)

    assert result["iterations"] == 2
    assert result["state"]["status"] == "max_iterations_reached"
    assert len(result["trace"]) == 2
    assert [entry["action"] for entry in result["trace"]] == ["think", "act"]


def test_run_agent_loop_returns_early_on_done_action():
    plan = [{"action": "think"}, {"action": "done"}, {"action": "act"}]
    context = {"sessionId": "sess-2"}

    result = run_agent_loop(plan=plan, max_iterations=5, context=context)

    assert result["iterations"] == 2
    assert result["state"]["status"] == "done"
    assert result["state"]["last_action"] == "done"
    assert [entry["action"] for entry in result["trace"]] == ["think", "done"]


def test_summarize_step_results_returns_waiting_approval_if_any_step_waiting():
    step_results = [
        {"stepId": "s1", "status": "SUCCEEDED"},
        {"stepId": "s2", "status": "WAITING_APPROVAL"},
    ]

    result = summarize_step_results(step_results)

    assert result["status"] == "WAITING_APPROVAL"
    assert result["stepResults"] == step_results


def test_summarize_step_results_returns_succeeded_when_all_succeeded():
    step_results = [
        {"stepId": "s1", "status": "SUCCEEDED"},
        {"stepId": "s2", "status": "SUCCEEDED"},
    ]

    result = summarize_step_results(step_results)

    assert result["status"] == "SUCCEEDED"
    assert result["stepResults"] == step_results


def test_summarize_step_results_returns_partial_for_mixed_non_waiting_results():
    step_results = [
        {"stepId": "s1", "status": "SUCCEEDED"},
        {"stepId": "s2", "status": "FAILED"},
    ]

    result = summarize_step_results(step_results)

    assert result["status"] == "PARTIAL"
    assert result["stepResults"] == step_results
