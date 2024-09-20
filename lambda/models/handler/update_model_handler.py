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

"""Handler for UpdateModel requests."""

import json
import os

from ..domain_objects import UpdateModelRequest, UpdateModelResponse
from ..exception import ModelNotFoundError
from .base_handler import BaseApiHandler
from .utils import to_lisa_model


class UpdateModelHandler(BaseApiHandler):
    """Handler class for UpdateModel requests."""

    def __call__(self, model_id: str, update_request: UpdateModelRequest) -> UpdateModelResponse:  # type: ignore
        """Call handler to update model metadata or scaling config based on user request."""
        ddb_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if not ddb_item:
            raise ModelNotFoundError(f"Model '{model_id}' was not found.")

        # package model ID and request payload into single payload for step functions
        state_machine_payload = {"model_id": model_id, "update_payload": update_request.model_dump()}
        self._stepfunctions.start_execution(
            stateMachineArn=os.environ["UPDATE_SFN_ARN"], input=json.dumps(state_machine_payload)
        )

        return UpdateModelResponse(model=to_lisa_model(ddb_item))
