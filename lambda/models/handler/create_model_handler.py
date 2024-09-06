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

"""Handler for CreateModel requests."""

import os

from models.exception import ModelAlreadyExistsError

from ..domain_objects import CreateModelRequest, CreateModelResponse, ModelStatus
from .base_handler import BaseApiHandler
from .utils import to_lisa_model


class CreateModelHandler(BaseApiHandler):
    """Handler class for CreateModel requests."""

    def __call__(self, create_request: CreateModelRequest) -> CreateModelResponse:  # type: ignore
        """Create model infrastructure and add model data to LiteLLM database."""
        model_id = create_request.modelId

        # If model exists in DDB, then fail out. ModelId must be unique.
        table_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if table_item:
            raise ModelAlreadyExistsError(f"Model '{model_id}' already exists. Please select another name.")

        self._stepfunctions.start_execution(
            stateMachineArn=os.environ["CREATE_SFN_ARN"], input=create_request.model_dump_json()
        )

        # Placeholder data until model data is persisted in database via state machine workflow
        lisa_model = to_lisa_model(
            {
                "model_name": model_id,
                "litellm_params": {
                    "model": create_request.modelName,
                },
                "model_info": {
                    "id": model_id,
                    "model_status": ModelStatus.CREATING,
                    "streaming": create_request.streaming,
                },
            }
        )
        return CreateModelResponse(model=lisa_model)
