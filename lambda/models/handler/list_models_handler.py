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

"""Handler for ListModels requests."""

from starlette.datastructures import Headers

from ..clients.litellm_client import LiteLLMClient
from ..domain_objects import LISAModel, ListModelsResponse, ModelStatus


class ListModelsHandler:
    """Handler class for ListModels requests."""

    def __init__(self, base_uri: str, headers: Headers):
        """Create ListModelsHandler with URI for accessing LiteLLM directly."""
        self._litellm_client = LiteLLMClient(base_uri=base_uri, headers=headers)

    def __call__(self) -> ListModelsResponse:
        """Call handler to get all models from LiteLLM database and transform results into API response format."""
        litellm_models = self._litellm_client.list_models()
        models_list = [
            LISAModel(
                ModelId=m["model_name"],
                ModelName=m["litellm_params"]["model"].removeprefix("openai/"),
                UniqueId=m["model_info"]["id"],
                Status=m["model_info"].get("model_status", ModelStatus.IN_SERVICE),
                ModelType=m["model_info"].get("model_type", "textgen"),
                Streaming=m["model_info"].get("streaming", False),
                ModelUrl=m["litellm_params"].get("api_base", None),
                ContainerConfig=m["model_info"].get("container_config", None),
                AutoScalingConfig=m["model_info"].get("autoscaling_config", None),
                LoadBalancerConfig=m["model_info"].get("loadbalancer_config", None),
            )
            for m in litellm_models
        ]
        return ListModelsResponse(Models=models_list)
