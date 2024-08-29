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

"""Common utility functions across all API handlers."""

from typing import Any, Dict

from ..domain_objects import LISAModel, ModelStatus


def to_lisa_model(model_dict: Dict[str, Any]) -> LISAModel:
    """Convert LiteLLM model dictionary to a LISAModel object."""
    return LISAModel(
        ModelId=model_dict["model_name"],
        ModelName=model_dict["litellm_params"]["model"].removeprefix("openai/"),
        UniqueId=model_dict["model_info"]["id"],
        Status=model_dict["model_info"].get("model_status", ModelStatus.IN_SERVICE),
        ModelType=model_dict["model_info"].get("model_type", "textgen"),
        Streaming=model_dict["model_info"].get("streaming", False),
        ModelUrl=model_dict["litellm_params"].get("api_base", None),
        ContainerConfig=model_dict["model_info"].get("container_config", None),
        AutoScalingConfig=model_dict["model_info"].get("autoscaling_config", None),
        LoadBalancerConfig=model_dict["model_info"].get("loadbalancer_config", None),
    )
