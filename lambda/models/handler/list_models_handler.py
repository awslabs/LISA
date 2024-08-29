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

from ..domain_objects import ListModelsResponse
from .base_handler import BaseApiHandler
from .utils import to_lisa_model


class ListModelsHandler(BaseApiHandler):
    """Handler class for ListModels requests."""

    def __call__(self) -> ListModelsResponse:  # type: ignore
        """Call handler to get all models from LiteLLM database and transform results into API response format."""
        litellm_models = self._litellm_client.list_models()
        models_list = [to_lisa_model(m) for m in litellm_models]
        return ListModelsResponse(Models=models_list)
