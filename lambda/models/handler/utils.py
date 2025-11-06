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

from typing import Any, Dict, List, Optional

from utilities.common_functions import validate_model_access

from ..domain_objects import LISAModel
from ..exception import InvalidStateTransitionError, ModelNotFoundError


def to_lisa_model(model_dict: Dict[str, Any]) -> LISAModel:
    """Convert DDB model entry dictionary to a LISAModel object."""
    model_dict["model_config"]["status"] = model_dict["model_status"]
    if "model_url" in model_dict:
        model_dict["model_config"]["modelUrl"] = model_dict["model_url"]
    lisa_model: LISAModel = LISAModel.model_validate(model_dict["model_config"])
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
        ModelNotFoundError: If model doesn't exist or user lacks access
    """
    model_response = model_table.get_item(Key={"model_id": model_id})
    if "Item" not in model_response:
        raise ModelNotFoundError(f"Model {model_id} not found")

    model_item = model_response["Item"]

    # Check if user has access to this model based on groups
    validate_model_access(model_item, model_id, user_groups, is_admin)

    return model_item


def get_model_and_validate_status(
    model_table,
    model_id: str,
    allowed_statuses: List[str] = None,
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
        ModelNotFoundError: If model doesn't exist or user lacks access
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
