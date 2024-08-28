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

"""Client for interfacing with the LiteLLM proxy's management options directly."""

from typing import Any, Dict, List

import requests
from starlette.datastructures import Headers


class LiteLLMClient:
    """Client definition for interfacing directly with LiteLLM management operations."""

    def __init__(self, base_uri: str, headers: Headers):
        self._base_uri = base_uri
        self._headers = headers

    def list_models(self) -> List[Dict[str, Any]]:
        """
        Retrieve all models from the database.

        Note, this is a superset of the models that are visible from the OpenAI API call to /models. If multiple models
        are defined with the same model name, only one will show in the OpenAI API call because of the model name, but
        both will show in the management API call because of the differences in unique IDs.
        """
        resp = requests.get(self._base_uri + "/model/info", headers=self._headers)
        all_models = resp.json()
        models_list: List[Dict[str, Any]] = all_models["data"]
        return models_list

    def add_model(self, model_name: str, litellm_params: Dict[str, str], additional_metadata: Dict[str, Any]) -> None:
        """
        Add a new model configuration to the database.

        The parameters for this method will be used for defining how LiteLLM accesses a model between both the model
        and the litellm_params dictionary, and anything that is not LiteLLM-specific can be added to the
        additional_metadata dictionary. Because LiteLLM uses this ID instead of other data, it is possible to add
        two models with the same name, which causes ambiguous results when using the OpenAI API for listing models as
        that only shows one model per model name.
        """
        requests.post(
            self._base_uri + "/model/new",
            headers=self._headers,
            json={"model_name": model_name, "litellm_params": litellm_params, "model_info": additional_metadata},
        )

    def delete_model(self, unique_id: str) -> None:
        """
        Delete a model from the database.

        The unique_id is the ID that LiteLLM generates on its end when creating a model, regardless of if the model
        was defined in a static configuration file or if it was added dynamically.
        """
        requests.post(self._base_uri + "/model/delete", headers=self._headers, json={"id": unique_id})
