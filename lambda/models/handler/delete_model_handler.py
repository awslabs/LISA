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

import boto3
from models.exception import ModelNotFoundError
from utilities.common_functions import retry_config

from ..domain_objects import DeleteModelResponse, ModelStatus
from .base_handler import BaseApiHandler
from .utils import to_lisa_model

stepfunctions = boto3.client("stepfunctions", region_name=os.environ["AWS_REGION"], config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"])


class DeleteModelHandler(BaseApiHandler):
    """Handler class for DeleteModel requests."""

    def __call__(self, unique_id: str) -> DeleteModelResponse:  # type: ignore
        """Kick off state machine to delete infrastructure and remove model reference from LiteLLM."""
        table_item = model_table.get_item(Key={"model_id": unique_id}).get("Item", None)
        if not table_item:
            raise ModelNotFoundError(f"Model '{unique_id}' was not found")

        stepfunctions.start_execution(
            stateMachineArn=os.environ["DELETE_SFN_ARN"], input=json.dumps({"model_id": unique_id})
        )

        # Placeholder info until all model info is properly stored in DDB
        lisa_model = to_lisa_model(
            {
                "model_name": unique_id,
                "litellm_params": {
                    "model": unique_id,
                },
                "model_info": {
                    "id": unique_id,
                    "model_status": ModelStatus.DELETING,
                },
            }
        )

        return DeleteModelResponse(Model=lisa_model)
