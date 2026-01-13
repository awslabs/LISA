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

import logging
from typing import Any, Dict, List, Optional

from utilities.auth import user_has_group_access
from utilities.validation import ValidationError

from ..domain_objects import GuardrailConfig, LISAModel
from ..exception import InvalidStateTransitionError, ModelNotFoundError

logger = logging.getLogger(__name__)


def to_lisa_model(model_dict: Dict[str, Any]) -> LISAModel:
    """Convert DDB model entry dictionary to a LISAModel object."""
    model_config = model_dict.get("model_config", {})
    model_config["status"] = model_dict.get("model_status", "Unknown")
    if "model_url" in model_dict:
        model_config["modelUrl"] = model_dict["model_url"]
    lisa_model: LISAModel = LISAModel.model_validate(model_config)
    return lisa_model


def get_model_and_validate_access(
    model_table, model_id: str, user_groups: Optional[List[str]] = None, is_admin: bool = False
) -> Dict[str, Any]:
    """
    Get model from DynamoDB and validate user access

    Args:
        model_table: DynamoDB table resource
        model_id: ID of the model to retrieve
        user_groups: User's group memberships
        is_admin: Whether user is admin

    Returns:
        Dict: Model item from DynamoDB

    Raises:
        ModelNotFoundError: If model doesn't exist
        ValidationError: If user doesn't have access to model
    """
    model_response = model_table.get_item(Key={"model_id": model_id})
    if "Item" not in model_response:
        raise ModelNotFoundError(f"Model {model_id} not found")

    model_item = model_response["Item"]

    # Check if user has access to this model based on groups
    if not is_admin:
        allowed_groups = model_item.get("model_config", {}).get("allowedGroups", [])
        user_groups = user_groups or []

        # Check if user has access
        if not user_has_group_access(user_groups, allowed_groups):
            raise ValidationError(f"Access denied to access model {model_id}")

    return model_item


def get_model_and_validate_status(
    model_table,
    model_id: str,
    allowed_statuses: List[str] | None = None,
    user_groups: Optional[List[str]] = None,
    is_admin: bool = False,
) -> Dict[str, Any]:
    """
    Get model from DynamoDB, validate user access, and check model status

    Args:
        model_table: DynamoDB table resource
        model_id: ID of the model to retrieve
        allowed_statuses: List of allowed model statuses for the operation
                         Defaults to ["InService", "Stopped"] for schedule operations
        user_groups: User's group memberships
        is_admin: Whether user is admin

    Returns:
        Dict: Model item from DynamoDB

    Raises:
        ModelNotFoundError: If model doesn't exist
        ValidationError: If user doesn't have access to model
        InvalidStateTransitionError: If model is not in allowed status
    """
    if allowed_statuses is None:
        allowed_statuses = ["InService", "Stopped"]

    model_item = get_model_and_validate_access(model_table, model_id, user_groups, is_admin)

    model_status = model_item.get("model_status")
    if model_status not in allowed_statuses:
        status_list = "', '".join(allowed_statuses)
        raise InvalidStateTransitionError(
            f"Cannot perform operation when model is in '{model_status}' state, "
            f"model must be in one of: '{status_list}'."
        )

    return model_item


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
