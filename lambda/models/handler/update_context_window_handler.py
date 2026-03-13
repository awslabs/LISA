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

"""Handler for UpdateContextWindow requests."""

from utilities.time import now

from ..domain_objects import UpdateContextWindowRequest, UpdateContextWindowResponse
from .base_handler import BaseApiHandler
from .utils import get_model_and_validate_access, to_lisa_model


class UpdateContextWindowHandler(BaseApiHandler):
    """Handler class for manually overriding a model's context window value."""

    def __call__(self, model_id: str, update_request: UpdateContextWindowRequest) -> UpdateContextWindowResponse:
        """Set the context_window attribute on the top-level DDB record for the given model."""
        model_item = get_model_and_validate_access(self._model_table, model_id, is_admin=True)

        self._model_table.update_item(
            Key={"model_id": model_id},
            UpdateExpression="SET context_window = :cw, last_modified_date = :lm",
            ExpressionAttributeValues={
                ":cw": update_request.contextWindow,
                ":lm": now(),
            },
        )

        # Reflect the new value in the returned model object
        model_item["context_window"] = update_request.contextWindow
        lisa_model = to_lisa_model(model_item)
        return UpdateContextWindowResponse(model=lisa_model)
