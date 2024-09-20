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

"""Lambda handlers for UpdateModel state machine."""


from copy import deepcopy
from typing import Any, Dict


def handle_job_intake(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle initial UpdateModel job submission.

    This handler will perform the following actions:
    1. Determine if any metadata (streaming, or modelType) changes are required
        1. If so, accumulate changes for a ddb update expression
    2. Determine if any AutoScaling changes are required
        1. If so, accumulate changes for a ddb update expression, set status to Updating
        2. If disabling or setting desired capacity to 0, then remove model entry from LiteLLM
            1. accumulate update expression to set the previous LiteLLM ID to null/None
    3. If any desired capacity changes are required, set a boolean value for a poll/wait loop on capacity changes
    4. Commit changes to the database
    """
    output_dict = deepcopy(event)
    output_dict["has_capacity_update"] = True
    return output_dict


def handle_poll_capacity(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Poll autoscaling and target group to confirm if the capacity is done updating.

    This handler will:
    1. Get the ASG's current status. If it is still updating, then exit with a boolean to indicate for more polling
    2. If the ASG status has completed, validate with the load balancer's target group that it also has the same
        number of healthy instances
    3. If both the ASG and target group healthy instances match, then discontinue polling
    """
    output_dict = deepcopy(event)
    output_dict["should_continue_capacity_polling"] = False
    return output_dict


def handle_finish_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Finalize update in DDB.

    1. If the model was enabled from the Stopped state, add the model back to LiteLLM, set status to InService in DDB
    2. If the model was disabled from the InService state, set status to Stopped
    3. Commit changes to DDB
    """
    return event
