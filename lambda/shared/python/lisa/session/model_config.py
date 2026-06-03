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

"""Helpers for refreshing a session's `selectedModel` against the latest model
configuration in the model table. Kept out of the session handlers so they are
unit-testable without API plumbing.
"""

import logging
from typing import Any

from botocore.exceptions import ClientError
from lisa.session.models import SelectedModelFeature, SessionConfigurationModel

logger = logging.getLogger(__name__)


def get_current_model_config(model_table: Any, model_id: str) -> dict[str, Any]:
    """Fetch the current configuration for a given model from the model table.

    Returns an empty dict when the table is unavailable, the model_id is empty,
    or the lookup fails — callers can branch on falsiness.
    """
    if not model_table or not model_id:
        return {}
    try:
        response = model_table.get_item(Key={"model_id": model_id})
        model_item = response.get("Item", {})
        return dict(model_item.get("model_config", {}))
    except ClientError as error:
        logger.warning(f"Could not fetch model config for {model_id}: {error}")
        return {}


def update_session_with_current_model_config(
    session_config: SessionConfigurationModel,
    model_table: Any,
) -> SessionConfigurationModel:
    """Refresh ``session_config.selectedModel`` against the latest model table entry.

    Returns the configuration unchanged if there is no selectedModel, no
    modelId, or the model lookup fails. Otherwise returns a copy with features,
    streaming, modelType, modelDescription, and allowedGroups updated.
    """
    if not session_config or not session_config.selectedModel:
        return session_config

    selected_model = session_config.selectedModel
    model_id = selected_model.modelId
    if not model_id:
        logger.warning("No modelId found in session selectedModel")
        return session_config

    current_model_config = get_current_model_config(model_table, model_id)
    if not current_model_config:
        logger.warning(f"Could not fetch current config for model {model_id}, using existing session config")
        return session_config

    updated_selected = selected_model.model_copy(deep=True)

    if "features" in current_model_config:
        updated_selected.features = [
            SelectedModelFeature.model_validate(f) if isinstance(f, dict) else f
            for f in current_model_config["features"]
        ]
    if "streaming" in current_model_config:
        updated_selected.streaming = current_model_config["streaming"]
    if "modelType" in current_model_config:
        updated_selected.modelType = str(current_model_config["modelType"])
    if "modelDescription" in current_model_config:
        updated_selected.modelDescription = current_model_config["modelDescription"]
    if "allowedGroups" in current_model_config:
        updated_selected.allowedGroups = current_model_config["allowedGroups"]

    logger.info(f"Updated session selectedModel config for model {model_id} with current model settings")
    updated_config: SessionConfigurationModel = session_config.model_copy(update={"selectedModel": updated_selected})
    return updated_config
