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

"""Handler for DeleteModel requests."""

import json
import os

from models.exception import ModelNotFoundError

from ..domain_objects import DeleteModelResponse, ModelStatus
from .base_handler import BaseApiHandler
from .utils import to_lisa_model


class DeleteModelHandler(BaseApiHandler):
    """Handler class for DeleteModel requests."""

    def __call__(self, model_id: str) -> DeleteModelResponse:  # type: ignore
        """Kick off state machine to delete infrastructure and remove model reference from LiteLLM."""
        table_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if not table_item:
            raise ModelNotFoundError(f"Model '{model_id}' was not found")

        self._stepfunctions.start_execution(
            stateMachineArn=os.environ["DELETE_SFN_ARN"], input=json.dumps({"modelId": model_id})
        )

        # Placeholder info until all model info is properly stored in DDB
        lisa_model = to_lisa_model(
            {
                "model_name": model_id,
                "litellm_params": {
                    "model": table_item["model_config"]["modelName"],
                },
                "model_info": {
                    "id": table_item["litellm_id"],
                    "model_status": ModelStatus.DELETING,
                    "streaming": table_item["model_config"]["streaming"],
                },
            }
        )

        return DeleteModelResponse(model=lisa_model)
