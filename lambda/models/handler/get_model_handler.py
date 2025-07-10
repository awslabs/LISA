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

from typing import List

from ..domain_objects import GetModelResponse
from ..exception import ModelNotFoundError
from .base_handler import BaseApiHandler
from .utils import to_lisa_model


class GetModelHandler(BaseApiHandler):
    """Handler class for GetModel requests."""

    def __call__(self, model_id: str, user_groups: List[str] = None, is_admin: bool = False) -> GetModelResponse:  # type: ignore
        """Get model metadata from LiteLLM and translate to a model management response object."""
        ddb_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if not ddb_item:
            raise ModelNotFoundError(f"Model '{model_id}' was not found.")
        
        model = to_lisa_model(ddb_item)
        
        # Check if user has access to this model based on groups
        if not is_admin and user_groups is not None:
            if not self._user_has_group_access(user_groups, model.allowedGroups or []):
                raise ModelNotFoundError(f"Model '{model_id}' was not found.")
        
        return GetModelResponse(model=model)
    
    def _user_has_group_access(self, user_groups: List[str], allowed_groups: List[str]) -> bool:
        """
        Check if user has access to a model based on group membership.
        
        Args:
            user_groups: List of groups the user belongs to
            allowed_groups: List of groups allowed to access the model
            
        Returns:
            True if user has access (either no restrictions or user has required group)
        """
        # Public Model
        if not allowed_groups:
            return True

        # Check if user has at least one matching group
        return len(set(user_groups).intersection(set(allowed_groups))) > 0
