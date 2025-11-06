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

"""Common utility functions across all API handlers."""

from typing import Any, Dict, List

from ..domain_objects import GuardrailConfig, LISAModel


def to_lisa_model(model_dict: Dict[str, Any]) -> LISAModel:
    """Convert DDB model entry dictionary to a LISAModel object."""
    model_dict["model_config"]["status"] = model_dict["model_status"]
    if "model_url" in model_dict:
        model_dict["model_config"]["modelUrl"] = model_dict["model_url"]
    lisa_model: LISAModel = LISAModel.model_validate(model_dict["model_config"])
    return lisa_model


def create_guardrail_config(item: Dict[str, Any]) -> GuardrailConfig:
    """Create a GuardrailConfig object from a DynamoDB guardrail item."""
    return GuardrailConfig(**item)


def attach_guardrails_to_model(model: LISAModel, guardrail_items: List[Dict[str, Any]]) -> None:
    """Build guardrails config from DDB items and attach to model."""
    if not guardrail_items:
        return

    model.guardrailsConfig = {
        f"guardrail-{item['guardrailName']}": create_guardrail_config(item) for item in guardrail_items
    }


def fetch_guardrails_for_model(guardrails_table, model_id: str) -> List[Dict[str, Any]]:
    """Query guardrails table for a specific model ID."""
    guardrails_response = guardrails_table.query(
        IndexName="ModelIdIndex",
        KeyConditionExpression="modelId = :modelId",
        ExpressionAttributeValues={":modelId": model_id},
    )
    return guardrails_response.get("Items", [])


def fetch_all_guardrails(guardrails_table) -> List[Dict[str, Any]]:
    """Scan all guardrails from the table with pagination."""
    all_guardrails = []
    guardrails_response = guardrails_table.scan()
    all_guardrails.extend(guardrails_response.get("Items", []))
    pagination_key = guardrails_response.get("LastEvaluatedKey", None)

    while pagination_key:
        guardrails_response = guardrails_table.scan(ExclusiveStartKey=pagination_key)
        all_guardrails.extend(guardrails_response.get("Items", []))
        pagination_key = guardrails_response.get("LastEvaluatedKey", None)

    return all_guardrails


def group_guardrails_by_model(guardrail_items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group guardrail items by modelId."""
    guardrails_by_model: Dict[str, List[Dict[str, Any]]] = {}
    for item in guardrail_items:
        model_id = item["modelId"]
        if model_id not in guardrails_by_model:
            guardrails_by_model[model_id] = []
        guardrails_by_model[model_id].append(item)

    return guardrails_by_model
