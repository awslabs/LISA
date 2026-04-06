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

"""Discovery helpers for Amazon Bedrock Agents (control plane)."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import boto3
from botocore.exceptions import ClientError
from models.domain_objects import BedrockAgentActionTool, BedrockAgentAliasSummary, BedrockAgentDiscoveryItem
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)

# Draft / test alias used by Bedrock for unpublished agent versions
TST_ALIAS_ID = "TSTALIASID"


def _pick_suggested_alias(aliases: list[BedrockAgentAliasSummary]) -> str | None:
    """Prefer the draft test alias, then the first PREPARED alias."""
    by_id = {a.agentAliasId: a for a in aliases}
    if TST_ALIAS_ID in by_id:
        return TST_ALIAS_ID
    for a in aliases:
        if a.agentAliasStatus == "PREPARED":
            return a.agentAliasId
    return aliases[0].agentAliasId if aliases else None


def _make_openai_tool_name(agent_id: str, action_group_id: str, function_name: str) -> str:
    """Stable unique OpenAI function name (<= 64 chars where possible)."""
    raw = f"bedrock_{agent_id}_{action_group_id}_{function_name}"
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", raw)
    if len(sanitized) <= 64:
        return sanitized
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    short = f"bedrock_{agent_id[:8]}_{digest}"
    return short[:64]


def _parameter_map_to_openai_schema(parameters: Any) -> dict[str, Any]:
    """Convert Bedrock function parameter map to OpenAI JSON Schema fragment."""
    if not isinstance(parameters, dict):
        return {"type": "object", "properties": {}, "required": []}
    # OpenAPI-style nested object
    if "properties" in parameters and isinstance(parameters.get("properties"), dict):
        req = parameters.get("required")
        if not isinstance(req, list):
            req = []
        return {"type": "object", "properties": dict(parameters["properties"]), "required": req}

    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, pdef in parameters.items():
        if not isinstance(pdef, dict):
            continue
        ptype = str(pdef.get("type") or "string").lower()
        json_type = "string"
        if ptype in ("integer", "int", "long"):
            json_type = "integer"
        elif ptype in ("number", "float", "double"):
            json_type = "number"
        elif ptype in ("boolean", "bool"):
            json_type = "boolean"
        elif ptype == "array":
            json_type = "array"
        elif ptype in ("object", "struct", "map"):
            json_type = "object"
        prop: dict[str, Any] = {"type": json_type}
        desc = pdef.get("description")
        if desc:
            prop["description"] = str(desc)
        if json_type == "object" and isinstance(pdef.get("properties"), dict):
            nested = _parameter_map_to_openai_schema(pdef)
            prop["properties"] = nested.get("properties", {})
            if nested.get("required"):
                prop["required"] = nested["required"]
        properties[pname] = prop
        if pdef.get("required") is True or pdef.get("isRequired") is True:
            required.append(pname)
    return {"type": "object", "properties": properties, "required": required}


def _tools_from_agent_action_group(
    agent_id: str,
    action_group_id: str,
    action_group_name: str,
    agent_action_group: dict[str, Any],
) -> list[BedrockAgentActionTool]:
    fs = agent_action_group.get("functionSchema")
    if not fs or not isinstance(fs, dict):
        return []

    funcs = fs.get("functions")
    if not funcs and isinstance(fs.get("memberFunctions"), dict):
        funcs = fs["memberFunctions"].get("functions")
    if not funcs or not isinstance(funcs, list):
        return []

    tools: list[BedrockAgentActionTool] = []
    for fn in funcs:
        if not isinstance(fn, dict):
            continue
        fname = fn.get("name")
        if not fname:
            continue
        desc = str(fn.get("description") or "")
        param_schema = _parameter_map_to_openai_schema(fn.get("parameters"))
        open_ai_name = _make_openai_tool_name(agent_id, action_group_id, str(fname))
        tools.append(
            BedrockAgentActionTool(
                openAiToolName=open_ai_name,
                functionName=str(fname),
                actionGroupId=action_group_id,
                actionGroupName=action_group_name or "",
                description=desc,
                parameterSchema=param_schema,
            )
        )
    return tools


def discover_agent_action_tools(
    agent_id: str,
    agent_version: str,
    bedrock_agent_client: Any,
) -> list[BedrockAgentActionTool]:
    """List ENABLED action groups and extract function-schema tools for an agent version."""
    if not agent_version or not str(agent_version).strip():
        return []
    tools: list[BedrockAgentActionTool] = []
    next_token: str | None = None
    try:
        while True:
            params: dict[str, Any] = {
                "agentId": agent_id,
                "agentVersion": agent_version,
                "maxResults": 100,
            }
            if next_token:
                params["nextToken"] = next_token
            page = bedrock_agent_client.list_agent_action_groups(**params)
            for summary in page.get("actionGroupSummaries", []):
                if summary.get("actionGroupState") != "ENABLED":
                    continue
                ag_id = summary.get("actionGroupId")
                if not ag_id:
                    continue
                try:
                    detail = bedrock_agent_client.get_agent_action_group(
                        agentId=agent_id,
                        agentVersion=agent_version,
                        actionGroupId=ag_id,
                    )
                except ClientError as e:
                    logger.warning("get_agent_action_group failed %s %s: %s", agent_id, ag_id, e)
                    continue
                ag = detail.get("agentActionGroup", {})
                if ag.get("actionGroupState") == "DISABLED":
                    continue
                ag_name = str(ag.get("actionGroupName") or summary.get("actionGroupName") or "")
                tools.extend(_tools_from_agent_action_group(agent_id, ag_id, ag_name, ag))
            next_token = page.get("nextToken")
            if not next_token:
                break
    except ClientError as e:
        logger.warning("list_agent_action_groups failed for %s: %s", agent_id, e)
        return []
    return tools


def list_agent_aliases(agent_id: str, bedrock_agent_client: Any) -> list[BedrockAgentAliasSummary]:
    """List all aliases for an agent (paginated)."""
    out: list[BedrockAgentAliasSummary] = []
    token: str | None = None
    while True:
        params: dict[str, Any] = {"agentId": agent_id, "maxResults": 100}
        if token:
            params["nextToken"] = token
        resp = bedrock_agent_client.list_agent_aliases(**params)
        for s in resp.get("agentAliasSummaries", []):
            out.append(BedrockAgentAliasSummary(**s))
        token = resp.get("nextToken")
        if not token:
            break
    return out


def discover_bedrock_agents(bedrock_agent_client: Any | None = None) -> list[BedrockAgentDiscoveryItem]:
    """
    List agents in the account and attach alias hints for invocation.

    Only agents in PREPARED state are returned (consistent with ready-to-invoke agents).
    """
    if not bedrock_agent_client:
        bedrock_agent_client = boto3.client("bedrock-agent")

    try:
        summaries: list[dict[str, Any]] = []
        next_token = None
        while True:
            params: dict[str, Any] = {"maxResults": 100}
            if next_token:
                params["nextToken"] = next_token
            response = bedrock_agent_client.list_agents(**params)
            summaries.extend(response.get("agentSummaries", []))
            next_token = response.get("nextToken")
            if not next_token:
                break

        items: list[BedrockAgentDiscoveryItem] = []
        for s in summaries:
            if s.get("agentStatus") != "PREPARED":
                continue
            agent_id = s["agentId"]
            try:
                aliases = list_agent_aliases(agent_id, bedrock_agent_client)
            except ClientError as e:
                logger.warning("Could not list aliases for agent %s: %s", agent_id, e)
                aliases = []
            suggested = _pick_suggested_alias(aliases)
            version = s.get("latestAgentVersion") or ""
            action_tools: list[BedrockAgentActionTool] = []
            if version:
                try:
                    action_tools = discover_agent_action_tools(agent_id, str(version), bedrock_agent_client)
                except Exception as e:
                    logger.warning("Action tool discovery failed for agent %s: %s", agent_id, e)
            items.append(
                BedrockAgentDiscoveryItem(
                    agentId=agent_id,
                    agentName=s.get("agentName", agent_id),
                    agentStatus=s.get("agentStatus", ""),
                    description=s.get("description") or "",
                    updatedAt=s.get("updatedAt"),
                    latestAgentVersion=s.get("latestAgentVersion"),
                    suggestedAliasId=suggested,
                    aliases=aliases,
                    invokeReady=bool(suggested),
                    actionTools=action_tools,
                )
            )

        logger.info("Discovered %s PREPARED Bedrock agents", len(items))
        return items

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "AccessDeniedException":
            raise ValidationError(
                "Access denied listing Bedrock Agents. Check IAM for bedrock:ListAgents and bedrock:ListAgentAliases."
            ) from e
        if error_code == "ThrottlingException":
            raise ValidationError("Rate limit exceeded while listing Bedrock Agents. Try again later.") from e
        raise ValidationError(f"Failed to list Bedrock Agents: {e!s}") from e
    except Exception as e:
        logger.error("Unexpected error listing Bedrock Agents: %s", e, exc_info=True)
        raise ValidationError(f"Unexpected error listing Bedrock Agents: {e!s}") from e
