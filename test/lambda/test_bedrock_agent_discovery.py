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

"""Tests for Bedrock Agent discovery utilities."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from lisa.domain.domain_objects import BedrockAgentAliasSummary
from lisa.utilities import bedrock_agent_discovery as bed_ad
from lisa.utilities.bedrock_agent_discovery import discover_bedrock_agents, list_agent_aliases, TST_ALIAS_ID
from lisa.utilities.validation import ValidationError


@pytest.fixture
def mock_bedrock_agent_client():
    return MagicMock()


def test_discover_prefers_tst_alias(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.return_value = {
        "agentSummaries": [
            {
                "agentId": "a1",
                "agentName": "Agent One",
                "agentStatus": "PREPARED",
                "description": "d",
            },
            {
                "agentId": "a2",
                "agentName": "Draft only",
                "agentStatus": "CREATING",
            },
        ]
    }

    def list_aliases_side_effect(**kwargs):
        aid = kwargs["agentId"]
        if aid == "a1":
            return {
                "agentAliasSummaries": [
                    {"agentAliasId": "OTHER", "agentAliasName": "prod", "agentAliasStatus": "PREPARED"},
                    {"agentAliasId": TST_ALIAS_ID, "agentAliasName": "draft", "agentAliasStatus": "PREPARED"},
                ]
            }
        return {"agentAliasSummaries": []}

    mock_bedrock_agent_client.list_agent_aliases.side_effect = list_aliases_side_effect

    result = discover_bedrock_agents(mock_bedrock_agent_client)

    assert len(result) == 1
    assert result[0].agentId == "a1"
    assert result[0].suggestedAliasId == TST_ALIAS_ID
    assert result[0].invokeReady is True


def test_discover_skips_non_prepared(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.return_value = {
        "agentSummaries": [
            {"agentId": "x", "agentName": "X", "agentStatus": "NOT_PREPARED"},
        ]
    }
    result = discover_bedrock_agents(mock_bedrock_agent_client)
    assert result == []
    mock_bedrock_agent_client.list_agent_aliases.assert_not_called()


def test_list_agent_aliases_pagination(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agent_aliases.side_effect = [
        {"agentAliasSummaries": [{"agentAliasId": "A", "agentAliasName": "a"}], "nextToken": "t"},
        {"agentAliasSummaries": [{"agentAliasId": "B", "agentAliasName": "b"}]},
    ]
    out = list_agent_aliases("agent-1", mock_bedrock_agent_client)
    assert [a.agentAliasId for a in out] == ["A", "B"]


def test_discover_access_denied(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "ListAgents"
    )
    with pytest.raises(ValidationError, match="Access denied"):
        discover_bedrock_agents(mock_bedrock_agent_client)


def test_discover_throttling(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "slow"}}, "ListAgents"
    )
    with pytest.raises(ValidationError, match="Rate limit"):
        discover_bedrock_agents(mock_bedrock_agent_client)


def test_discover_generic_client_error(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.side_effect = ClientError(
        {"Error": {"Code": "InternalServerException", "Message": "x"}}, "ListAgents"
    )
    with pytest.raises(ValidationError, match="Failed to list Bedrock Agents"):
        discover_bedrock_agents(mock_bedrock_agent_client)


def test_discover_unexpected_error(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.side_effect = RuntimeError("boom")
    with pytest.raises(ValidationError, match="Unexpected error listing Bedrock Agents"):
        discover_bedrock_agents(mock_bedrock_agent_client)


def test_discover_list_agents_pagination(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.side_effect = [
        {
            "agentSummaries": [
                {
                    "agentId": "a1",
                    "agentName": "A",
                    "agentStatus": "PREPARED",
                    "latestAgentVersion": "1",
                }
            ],
            "nextToken": "t1",
        },
        {
            "agentSummaries": [
                {
                    "agentId": "a2",
                    "agentName": "B",
                    "agentStatus": "PREPARED",
                    "latestAgentVersion": "1",
                }
            ],
        },
    ]
    mock_bedrock_agent_client.list_agent_aliases.return_value = {"agentAliasSummaries": []}

    def empty_action_groups(**_kwargs):
        return {"actionGroupSummaries": []}

    mock_bedrock_agent_client.list_agent_action_groups.side_effect = empty_action_groups
    result = discover_bedrock_agents(mock_bedrock_agent_client)
    assert len(result) == 2
    assert {r.agentId for r in result} == {"a1", "a2"}


def test_discover_alias_list_error_still_returns_agent(mock_bedrock_agent_client):
    mock_bedrock_agent_client.list_agents.return_value = {
        "agentSummaries": [
            {
                "agentId": "a1",
                "agentName": "A",
                "agentStatus": "PREPARED",
                "latestAgentVersion": "1",
            }
        ]
    }
    mock_bedrock_agent_client.list_agent_aliases.side_effect = ClientError(
        {"Error": {"Code": "x", "Message": "m"}}, "ListAgentAliases"
    )
    mock_bedrock_agent_client.list_agent_action_groups.return_value = {"actionGroupSummaries": []}
    result = discover_bedrock_agents(mock_bedrock_agent_client)
    assert len(result) == 1
    assert result[0].aliases == []
    assert result[0].invokeReady is False


def test_pick_suggested_alias_first_prepared_without_tst():
    aliases = [
        BedrockAgentAliasSummary(agentAliasId="P1", agentAliasName="p", agentAliasStatus="PREPARED"),
    ]
    assert bed_ad._pick_suggested_alias(aliases) == "P1"


def test_pick_suggested_alias_fallback_first_id():
    aliases = [
        BedrockAgentAliasSummary(agentAliasId="Z1", agentAliasName="z", agentAliasStatus="NOT_PREPARED"),
    ]
    assert bed_ad._pick_suggested_alias(aliases) == "Z1"


def test_pick_suggested_alias_empty():
    assert bed_ad._pick_suggested_alias([]) is None


def test_make_openai_tool_name_short():
    n = bed_ad._make_openai_tool_name("aid", "gid", "my_func")
    assert n.startswith("bedrock_")
    assert len(n) <= 64


def test_make_openai_tool_name_hashes_when_long():
    long_id = "x" * 80
    n = bed_ad._make_openai_tool_name(long_id, "g" * 40, "fn")
    assert len(n) <= 64
    assert "bedrock_" in n


def test_parameter_map_to_openai_schema_non_dict():
    out = bed_ad._parameter_map_to_openai_schema(None)
    assert out["type"] == "object"
    assert out["properties"] == {}


def test_parameter_map_to_openai_schema_openapi_style():
    out = bed_ad._parameter_map_to_openai_schema(
        {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    )
    assert "a" in out["properties"]
    assert "a" in out["required"]


def test_parameter_map_to_openai_schema_flat_types():
    out = bed_ad._parameter_map_to_openai_schema(
        {
            "n": {"type": "integer"},
            "f": {"type": "float"},
            "b": {"type": "boolean"},
            "arr": {"type": "array"},
            "obj": {"type": "object", "properties": {"k": {"type": "string"}}, "required": ["k"]},
            "req": {"type": "string", "isRequired": True},
        }
    )
    assert out["properties"]["n"]["type"] == "integer"
    assert out["properties"]["f"]["type"] == "number"
    assert out["properties"]["b"]["type"] == "boolean"
    assert out["properties"]["arr"]["type"] == "array"
    assert "k" in out["properties"]["obj"].get("properties", {})
    assert "req" in out["required"]


def test_tools_from_agent_action_group_member_functions():
    ag = {
        "functionSchema": {
            "memberFunctions": {
                "functions": [
                    {"name": "do_x", "description": "d", "parameters": {"zip": {"type": "string", "required": True}}},
                ]
            }
        }
    }
    tools = bed_ad._tools_from_agent_action_group("agent-1", "ag-1", "Group", ag)
    assert len(tools) == 1
    assert tools[0].functionName == "do_x"
    assert tools[0].actionGroupId == "ag-1"


def test_tools_from_agent_action_group_skips_invalid_entries():
    assert bed_ad._tools_from_agent_action_group("a", "g", "n", {}) == []
    assert bed_ad._tools_from_agent_action_group("a", "g", "n", {"functionSchema": {}}) == []
    assert (
        bed_ad._tools_from_agent_action_group(
            "a",
            "g",
            "n",
            {"functionSchema": {"functions": [{"description": "no name"}, "not-a-dict"]}},
        )
        == []
    )


def test_discover_agent_action_tools_empty_version():
    assert bed_ad.discover_agent_action_tools("a", "", MagicMock()) == []
    assert bed_ad.discover_agent_action_tools("a", "   ", MagicMock()) == []


def test_discover_agent_action_tools_skips_disabled_and_errors():
    mock_c = MagicMock()
    mock_c.list_agent_action_groups.return_value = {
        "actionGroupSummaries": [
            {"actionGroupId": "skip", "actionGroupState": "DISABLED"},
            {"actionGroupId": "ok", "actionGroupState": "ENABLED"},
        ]
    }

    def get_ag(**kwargs):
        if kwargs["actionGroupId"] == "ok":
            return {
                "agentActionGroup": {
                    "actionGroupState": "ENABLED",
                    "actionGroupName": "AG",
                    "functionSchema": {"functions": [{"name": "f1", "parameters": {}}]},
                }
            }
        return {}

    mock_c.get_agent_action_group.side_effect = get_ag
    tools = bed_ad.discover_agent_action_tools("agent-x", "1", mock_c)
    assert len(tools) == 1
    assert tools[0].functionName == "f1"


def test_discover_agent_action_tools_get_group_client_error():
    mock_c = MagicMock()
    mock_c.list_agent_action_groups.return_value = {
        "actionGroupSummaries": [{"actionGroupId": "ag1", "actionGroupState": "ENABLED"}]
    }
    mock_c.get_agent_action_group.side_effect = ClientError({"Error": {"Code": "x"}}, "GetAgentActionGroup")
    assert bed_ad.discover_agent_action_tools("a", "1", mock_c) == []


def test_discover_agent_action_tools_list_groups_client_error():
    mock_c = MagicMock()
    mock_c.list_agent_action_groups.side_effect = ClientError({"Error": {"Code": "x"}}, "ListAgentActionGroups")
    assert bed_ad.discover_agent_action_tools("a", "1", mock_c) == []


def test_discover_agent_action_tools_detail_disabled():
    mock_c = MagicMock()
    mock_c.list_agent_action_groups.return_value = {
        "actionGroupSummaries": [{"actionGroupId": "ag1", "actionGroupState": "ENABLED"}]
    }
    mock_c.get_agent_action_group.return_value = {"agentActionGroup": {"actionGroupState": "DISABLED"}}
    assert bed_ad.discover_agent_action_tools("a", "1", mock_c) == []
