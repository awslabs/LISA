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

from ..domain_objects import ModelStatus, UpdateModelRequest, UpdateModelResponse
from ..exception import InvalidStateTransitionError, ModelNotFoundError
from .base_handler import BaseApiHandler
from .utils import attach_guardrails_to_model, fetch_guardrails_for_model, to_lisa_model


class UpdateModelHandler(BaseApiHandler):
    """Handler class for UpdateModel requests."""

    def __call__(self, model_id: str, update_request: UpdateModelRequest) -> UpdateModelResponse:  # type: ignore
        """Call handler to update model metadata or scaling config based on user request."""
        ddb_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if not ddb_item:
            raise ModelNotFoundError(f"Model '{model_id}' was not found.")

        model_status = ddb_item["model_status"]

        # Validations

        # Validate model is not actively mutating or failed before starting
        if model_status not in (ModelStatus.IN_SERVICE, ModelStatus.STOPPED):
            raise InvalidStateTransitionError(
                f"Model cannot be updated when it is not in the '{ModelStatus.IN_SERVICE}' or "
                f"'{ModelStatus.STOPPED}' states"
            )

        # Validate model mutations while enabling/disabling option is enabled
        if update_request.enabled is not None:
            # Force capacity changes and enable/disable operations to happen in separate requests
            if update_request.autoScalingInstanceConfig is not None:
                raise ValueError("Start or Stop operations and AutoScaling changes must happen in separate requests.")
            # Model cannot be enabled if it isn't already stopped
            if update_request.enabled and not model_status == ModelStatus.STOPPED:
                raise InvalidStateTransitionError(
                    f"Model cannot be enabled when it is not in the '{ModelStatus.STOPPED}' state."
                )
            # Model cannot be stopped if it isn't already in service
            elif not update_request.enabled and not model_status == ModelStatus.IN_SERVICE:
                raise InvalidStateTransitionError(
                    f"Model cannot be stopped when it is not in the '{ModelStatus.IN_SERVICE}' state."
                )

        # Validate values relative to current ASG. All conflicting request values have been validated as part of the
        # AutoScalingInstanceConfig model validations, so those are not duplicated here.
        if update_request.autoScalingInstanceConfig is not None:
            current_asg = ddb_item.get("auto_scaling_group", "")
            if not current_asg:
                raise ValueError("Cannot update AutoScaling Config for model not hosted in LISA infrastructure.")
            asg_config = update_request.autoScalingInstanceConfig
            model_asg_resp = self._autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[current_asg])
            model_asg = model_asg_resp["AutoScalingGroups"][0]

            # Desired capacity cannot be less than min or greater than max on deployed ASG
            if asg_config.desiredCapacity is not None:
                if asg_config.maxCapacity is None and asg_config.desiredCapacity > model_asg["MaxSize"]:
                    raise ValueError(f"Desired capacity cannot exceed ASG max of {model_asg['MaxSize']}.")
                if asg_config.minCapacity is None and asg_config.desiredCapacity < model_asg["MinSize"]:
                    raise ValueError(f"Desired capacity cannot be less than ASG min of {model_asg['MinSize']}.")

            # Min capacity can't be greater than the deployed ASG's max capacity
            if asg_config.minCapacity is not None:
                if asg_config.maxCapacity is None and asg_config.minCapacity > model_asg["MaxSize"]:
                    raise ValueError(f"Min capacity cannot exceed ASG max of {model_asg['MaxSize']}.")
                # Note: there is explicitly not a validation for minSize > existing desiredCapacity because
                # setting the min will update desired capacity if needed if the request is valid.

            # Max capacity can't be less than the deployed ASG's min capacity
            if asg_config.maxCapacity is not None:
                if asg_config.minCapacity is None and asg_config.maxCapacity < model_asg["MinSize"]:
                    raise ValueError(f"Max capacity cannot be less than ASG min of {model_asg['MinSize']}.")

        # Validate containerConfig updates
        if update_request.containerConfig is not None:
            current_asg = ddb_item.get("auto_scaling_group", "")
            if not current_asg:
                raise ValueError("Cannot update Container Config for model not hosted in LISA infrastructure.")

            # Validate that containerConfig exists in the current model
            current_container_config = ddb_item.get("model_config", {}).get("containerConfig", None)
            if not current_container_config:
                raise ValueError(
                    "Cannot update Container Config for model that was not originally configured with a container."
                )

        # Post-validation. Send work to state machine.

        # package model ID and request payload into single payload for step functions
        state_machine_payload = {"model_id": model_id, "update_payload": update_request.model_dump()}
        self._stepfunctions.start_execution(
            stateMachineArn=os.environ["UPDATE_SFN_ARN"], input=json.dumps(state_machine_payload)
        )

        model = to_lisa_model(ddb_item)

        # Fetch and attach guardrails for this model
        guardrail_items = fetch_guardrails_for_model(self._guardrails_table, model_id)
        attach_guardrails_to_model(model, guardrail_items)

        return UpdateModelResponse(model=model)
