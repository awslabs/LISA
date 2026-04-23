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

from typing import Any

import requests  # type: ignore[import-untyped,unused-ignore]
from starlette.datastructures import Headers

from ..exception import ModelNotFoundError


class LiteLLMClient:
    """Client definition for interfacing directly with LiteLLM management operations."""

    def __init__(self, base_uri: str, headers: Headers, verify: str | bool, timeout: int = 30):
        self._base_uri = base_uri
        self._headers = headers
        self._timeout = timeout
        self._verify = verify

    def list_models(self) -> list[dict[str, Any]]:
        """
        Retrieve all models from the database.

        Note, this is a superset of the models that are visible from the OpenAI API call to /models. If multiple models
        are defined with the same model name, only one will show in the OpenAI API call because of the model name, but
        both will show in the management API call because of the differences in unique IDs.
        """
        resp = requests.get(
            self._base_uri + "/model/info",
            headers=self._headers,
            timeout=self._timeout,
            verify=self._verify,
        )
        all_models = resp.json()
        models_list: list[dict[str, Any]] = all_models["data"]
        return models_list

    def add_model(self, model_name: str, litellm_params: dict[str, str]) -> dict[str, Any]:
        """
        Add a new model configuration to the database.

        The parameters for this method will be used for defining how LiteLLM accesses a model between both the model
        and the litellm_params dictionary, and anything that is not LiteLLM-specific can be added to the
        additional_metadata dictionary. Because LiteLLM uses this ID instead of other data, it is possible to add
        two models with the same name, which causes ambiguous results when using the OpenAI API for listing models as
        that only shows one model per model name.
        """
        resp = requests.post(
            self._base_uri + "/model/new",
            headers=self._headers,
            json={
                "model_name": model_name,
                "litellm_params": litellm_params,
            },
            timeout=self._timeout,
            verify=self._verify,
        )
        return resp.json()  # type: ignore [no-any-return]

    def delete_model(self, identifier: str) -> None:
        """
        Delete a model from the database.

        The identifier is the ID that LiteLLM generates on its end when creating a model, regardless of if the model
        was defined in a static configuration file or if it was added dynamically.
        """
        requests.post(
            self._base_uri + "/model/delete",
            headers=self._headers,
            json={"id": identifier},
            timeout=self._timeout,
            verify=self._verify,
        )

    def get_model(self, identifier: str) -> dict[str, Any]:
        """
        Get model metadata from the database.

        Due to what appears to be a bug in LiteLLM when accessing individual models from the /model/info route, we must
        list all models then filter out the one we want for this method call.
        """
        all_models = self.list_models()
        filtered_models = [m for m in all_models if m["model_info"]["id"] == identifier]
        if len(filtered_models) < 1:
            raise ModelNotFoundError("Specified model was not found.")
        return filtered_models[0]

    def create_guardrail(self, guardrail_config: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new guardrail configuration in LiteLLM.

        Args:
            guardrail_config: Dictionary containing guardrail configuration including
                            guardrail_name, guardrail_identifier, guardrail_version, mode, etc.

        Returns:
            Dictionary containing the created guardrail information including LiteLLM guardrail ID
        """
        resp = requests.post(
            self._base_uri + "/guardrails",
            headers=self._headers,
            json=guardrail_config,
            timeout=self._timeout,
            verify=self._verify,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore [no-any-return]

    def update_guardrail(self, guardrail_id: str, guardrail_config: dict[str, Any]) -> dict[str, Any]:
        """
        Update an existing guardrail configuration in LiteLLM.

        Args:
            guardrail_id: The LiteLLM guardrail ID to update
            guardrail_config: Dictionary containing updated guardrail configuration

        Returns:
            Dictionary containing the updated guardrail information
        """
        resp = requests.put(
            self._base_uri + f"/guardrails/{guardrail_id}",
            headers=self._headers,
            json=guardrail_config,
            timeout=self._timeout,
            verify=self._verify,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore [no-any-return]

    def delete_guardrail(self, guardrail_id: str) -> None:
        """
        Delete a guardrail configuration from LiteLLM.

        Args:
            guardrail_id: The LiteLLM guardrail ID to delete
        """
        resp = requests.delete(
            self._base_uri + f"/guardrails/{guardrail_id}",
            headers=self._headers,
            timeout=self._timeout,
            verify=self._verify,
        )
        resp.raise_for_status()

    def get_guardrail_info(self, guardrail_id: str) -> dict[str, Any]:
        """
        Get information about a specific guardrail.

        Args:
            guardrail_id: The LiteLLM guardrail ID to retrieve

        Returns:
            Dictionary containing guardrail information
        """
        resp = requests.get(
            self._base_uri + f"/guardrails/{guardrail_id}",
            headers=self._headers,
            timeout=self._timeout,
            verify=self._verify,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore [no-any-return]

    def apply_guardrail(self, guardrail_name: str, text: str) -> dict[str, Any]:
        """
        Apply a guardrail to text content for validation.

        Args:
            guardrail_name: Name of the guardrail to apply
            text: Text content to validate against the guardrail

        Returns:
            Dictionary containing validation results
        """
        resp = requests.post(
            self._base_uri + "/guardrails/apply_guardrail",
            headers=self._headers,
            json={"guardrail_name": guardrail_name, "text": text},
            timeout=self._timeout,
            verify=self._verify,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore [no-any-return]
