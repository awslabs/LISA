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

import boto3
import os

from ..domain_objects import CreateModelRequest, CreateModelResponse, ModelStatus
from .base_handler import BaseApiHandler
from .utils import to_lisa_model
from utilities.common_functions import retry_config
from models.exception import ModelAlreadyExistsError

stepfunctions = boto3.client("stepfunctions", region_name=os.environ["AWS_REGION"], config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"])


class CreateModelHandler(BaseApiHandler):
    """Handler class for CreateModel requests."""

    def __call__(self, create_request: CreateModelRequest) -> CreateModelResponse:  # type: ignore
        """Create model infrastructure and add model data to LiteLLM database."""
        unique_id = create_request.ModelId

        # If model exists in DDB, then fail out. ModelId must be unique.
        table_item = model_table.get_item(Key={"model_id": unique_id}).get("Item", None)
        if table_item:
            raise ModelAlreadyExistsError(f"Model '{unique_id}' already exists. Please select another name.")

        stepfunctions.start_execution(
            stateMachineArn=os.environ["CREATE_SFN_ARN"], input=create_request.model_dump_json()
        )

        # Placeholder data until model data is persisted in database via state machine workflow
        lisa_model = to_lisa_model(
            {
                "model_name": unique_id,
                "litellm_params": {
                    "model": unique_id,
                },
                "model_info": {
                    "id": unique_id,
                    "model_status": ModelStatus.CREATING,
                },
            }
        )
        return CreateModelResponse(Model=lisa_model)
