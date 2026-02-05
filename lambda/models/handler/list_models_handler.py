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

"""Handler for ListModels requests."""


from utilities.auth import user_has_group_access

from ..domain_objects import ListModelsResponse
from .base_handler import BaseApiHandler
from .utils import attach_guardrails_to_model, fetch_all_guardrails, group_guardrails_by_model, to_lisa_model


class ListModelsHandler(BaseApiHandler):
    """Handler class for ListModels requests."""

    def __call__(self, user_groups: list[str] | None = None, is_admin: bool = False) -> ListModelsResponse:
        """Call handler to get all models from DynamoDB and transform results into API response format."""
        ddb_models = []
        models_response = self._model_table.scan()
        ddb_models.extend(models_response.get("Items", []))
        pagination_key = models_response.get("LastEvaluatedKey", None)
        while pagination_key:
            models_response = self._model_table.scan(ExclusiveStartKey=pagination_key)
            ddb_models.extend(models_response.get("Items", []))
            pagination_key = models_response.get("LastEvaluatedKey", None)

        models_list = [to_lisa_model(m) for m in ddb_models]

        # Fetch all guardrails and group them by model ID
        all_guardrails = fetch_all_guardrails(self._guardrails_table)
        guardrails_by_model = group_guardrails_by_model(all_guardrails)

        # Attach guardrails to models
        for model in models_list:
            if model.modelId in guardrails_by_model:
                attach_guardrails_to_model(model, guardrails_by_model[model.modelId])

        # Filter models based on user groups if not admin
        if not is_admin and user_groups is not None:
            models_list = [
                model for model in models_list if user_has_group_access(user_groups, model.allowedGroups or [])
            ]

        return ListModelsResponse(models=models_list)
