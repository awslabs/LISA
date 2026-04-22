"""Execution engine for workflow orchestration multi-step runs."""

from __future__ import annotations

import uuid
from typing import Any


def _run_tool_step(step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "runner": "tool",
        "message": f"Executed tool step '{step.get('name', step.get('stepId', 'unknown-step'))}'",
        "context": {"workflowId": ctx.get("workflowId"), "executionId": ctx.get("executionId")},
    }


def _run_llm_step(step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "runner": "llm",
        "message": f"Executed llm step '{step.get('name', step.get('stepId', 'unknown-step'))}'",
        "context": {"workflowId": ctx.get("workflowId"), "executionId": ctx.get("executionId")},
    }


def _build_approval_token(step: dict[str, Any], ctx: dict[str, Any]) -> str:
    workflow_id = str(ctx.get("workflowId", "workflow"))
    execution_id = str(ctx.get("executionId", "execution"))
    step_id = str(step.get("stepId", "step"))
    return f"approval::{workflow_id}::{execution_id}::{step_id}::{uuid.uuid4().hex}"


def execute_step(step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Execute a workflow step and return normalized status payload."""
    step_type = str(step.get("type", "")).lower()
    step_id = str(step.get("stepId", ""))

    if step_type == "tool":
        return {
            "stepId": step_id,
            "type": "tool",
            "status": "SUCCEEDED",
            "output": _run_tool_step(step, ctx),
        }

    if step_type == "approval":
        return {
            "stepId": step_id,
            "type": "approval",
            "status": "WAITING_APPROVAL",
            "approvalToken": _build_approval_token(step, ctx),
        }

    if step_type == "llm":
        return {
            "stepId": step_id,
            "type": "llm",
            "status": "SUCCEEDED",
            "output": _run_llm_step(step, ctx),
        }

    raise ValueError(f"Unknown step type: {step.get('type')}")


def summarize_step_results(step_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive final workflow status from collected per-step results."""
    statuses = [str(result.get("status", "")) for result in step_results]
    if any(status == "WAITING_APPROVAL" for status in statuses):
        final_status = "WAITING_APPROVAL"
    elif statuses and all(status == "SUCCEEDED" for status in statuses):
        final_status = "SUCCEEDED"
    else:
        final_status = "PARTIAL"
    return {
        "status": final_status,
        "stepResults": step_results,
    }


def run_agent_loop(plan: list[dict[str, Any]], max_iterations: int, context: dict[str, Any]) -> dict[str, Any]:
    """Run a bounded, deterministic agent loop over plan actions."""
    iterations = 0
    trace: list[dict[str, Any]] = []
    state: dict[str, Any] = {
        "status": "idle",
        "last_action": None,
        "context": dict(context),
    }

    if max_iterations <= 0:
        state["status"] = "max_iterations_reached"
        return {"state": state, "iterations": iterations, "trace": trace}

    for action_step in plan:
        if iterations >= max_iterations:
            break

        action = str(action_step.get("action", ""))
        iterations += 1
        state["last_action"] = action
        trace.append({"iteration": iterations, "action": action})

        if action == "done":
            state["status"] = "done"
            return {"state": state, "iterations": iterations, "trace": trace}

    state["status"] = "max_iterations_reached" if iterations >= max_iterations else "plan_exhausted"
    return {"state": state, "iterations": iterations, "trace": trace}
