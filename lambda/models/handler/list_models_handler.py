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

from typing import List, Optional

from ..domain_objects import ListModelsResponse
from .base_handler import BaseApiHandler
from .utils import to_lisa_model


class ListModelsHandler(BaseApiHandler):
    """Handler class for ListModels requests."""

    def __call__(self, user_groups: Optional[List[str]] = None, is_admin: bool = False) -> ListModelsResponse:
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

        # Filter models based on user groups if not admin
        if not is_admin and user_groups is not None:
            models_list = [
                model for model in models_list if self._user_has_group_access(user_groups, model.allowedGroups or [])
            ]

        return ListModelsResponse(models=models_list)

    def _user_has_group_access(self, user_groups: List[str], allowed_groups: List[str]) -> bool:
        """
        Check if user has access to a model based on group membership.

        Args:
            user_groups: List of groups the user belongs to
            allowed_groups: List of groups allowed to access the model

        Returns:
            True if user has access (either no restrictions or user has required group)
        """
        # Model is public
        if not allowed_groups:
            return True

        # Check if user has at least one matching group
        return len(set(user_groups).intersection(set(allowed_groups))) > 0
