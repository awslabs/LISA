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

"""Lambda handlers for CreateModel state machine."""

from copy import deepcopy
from typing import Any, Dict


def handle_set_model_to_creating(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set DDB entry to CREATING status."""
    output_dict = deepcopy(event)
    output_dict["create_infra"] = True
    return output_dict


def handle_start_copy_docker_image(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start process for copying Docker image into local AWS account."""
    output_dict = deepcopy(event)
    return output_dict


def handle_poll_docker_image_available(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check that Docker image is available in account or not."""
    output_dict = deepcopy(event)
    output_dict["continue_polling_docker"] = False
    return output_dict


def handle_start_create_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start model infrastructure creation."""
    output_dict = deepcopy(event)
    return output_dict


def handle_poll_create_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check that model infrastructure creation has completed or not."""
    output_dict = deepcopy(event)
    output_dict["continue_polling_stack"] = False
    return output_dict


def handle_add_model_to_litellm(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Add model to LiteLLM once it is created."""
    output_dict = deepcopy(event)
    return output_dict
