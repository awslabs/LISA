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

"""Handler for GetModel requests."""


from utilities.auth import user_has_group_access

from ..domain_objects import GetModelResponse
from ..exception import ModelNotFoundError
from .base_handler import BaseApiHandler
from .utils import attach_guardrails_to_model, fetch_guardrails_for_model, to_lisa_model


class GetModelHandler(BaseApiHandler):
    """Handler class for GetModel requests."""

    def __call__(self, model_id: str, user_groups: list[str] | None = None, is_admin: bool = False) -> GetModelResponse:
        """Get model metadata from LiteLLM and translate to a model management response object."""
        ddb_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if not ddb_item:
            raise ModelNotFoundError(f"Model '{model_id}' was not found.")

        model = to_lisa_model(ddb_item)

        # Fetch and attach guardrails for this model
        guardrail_items = fetch_guardrails_for_model(self._guardrails_table, model_id)
        attach_guardrails_to_model(model, guardrail_items)

        # Check if user has access to this model based on groups
        if not is_admin and user_groups is not None:
            if not user_has_group_access(user_groups, model.allowedGroups or []):
                raise ModelNotFoundError(f"Model '{model_id}' was not found.")

        return GetModelResponse(model=model)
