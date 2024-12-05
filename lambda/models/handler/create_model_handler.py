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

        # The below check ensures that the model is LISA hosted
        if (
            create_request.containerConfig is not None
            and create_request.autoScalingConfig is not None
            and create_request.loadBalancerConfig is not None
        ):
            if create_request.containerConfig.image.baseImage is None:
                raise ValueError("Base image must be provided for LISA hosted model.")

        # Validate values relative to current ASG. All conflicting request values have been validated as part of the
        # AutoScalingInstanceConfig model validations, so those are not duplicated here.
        if create_request.autoScalingConfig is not None:
            # Min capacity can't be greater than the deployed ASG's max capacity
            if create_request.autoScalingConfig.minCapacity is not None:
                if (
                    create_request.autoScalingConfig.maxCapacity is not None
                    and create_request.autoScalingConfig.minCapacity > create_request.autoScalingConfig.maxCapacity
                ):
                    raise ValueError(
                        f"Min capacity cannot exceed ASG max of {create_request.autoScalingConfig.maxCapacity}."
                    )

            # Max capacity can't be less than the deployed ASG's min capacity
            if create_request.autoScalingConfig.maxCapacity is not None:
                if (
                    create_request.autoScalingConfig.minCapacity is not None
                    and create_request.autoScalingConfig.maxCapacity < create_request.autoScalingConfig.minCapacity
                ):
                    raise ValueError(
                        f"Max capacity cannot be less than ASG min of {create_request.autoScalingConfig.minCapacity}."
                    )

        self._stepfunctions.start_execution(
            stateMachineArn=os.environ["CREATE_SFN_ARN"], input=create_request.model_dump_json()
        )

        lisa_model = to_lisa_model(
            {
                "model_config": create_request.model_dump(),
                "model_status": ModelStatus.CREATING,
            }
        )
        return CreateModelResponse(model=lisa_model)
