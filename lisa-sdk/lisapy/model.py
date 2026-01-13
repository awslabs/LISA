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


from .common import BaseMixin
from .errors import parse_error


class ModelMixin(BaseMixin):
    """Mixin for model-related operations."""

    def list_models(self) -> list[dict]:
        response = self._session.get(f"{self.url}/models")
        if response.status_code == 200:
            json_models = response.json()
            models: list[dict] = json_models.get("models")
            return models
        else:
            raise parse_error(response.status_code, response)

    def list_embedding_models(self) -> list[dict]:
        models = self.list_models()
        embeddings = [model for model in models if "embedding" == model["modelType"]]
        return embeddings

    def list_instances(self) -> list[str]:
        response = self._session.get(f"{self.url}/models/metadata/instances")
        if response.status_code == 200:
            json_instances: list[str] = response.json()
            return json_instances
        else:
            raise parse_error(response.status_code, response)

    def create_bedrock_model(self, payload: dict) -> dict:
        """Create a Bedrock model configuration.

        Args:
            payload: JSON payload for the Bedrock model

        Returns:
            Dict: Created model information

        Raises:
            Exception: If the request fails
        """
        response = self._session.post(f"{self.url}/models", json=payload)
        if response.status_code in [200, 201]:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def create_self_hosted_model(self, payload: dict) -> dict:
        """Create a self-hosted model configuration.

        Args:
            payload: JSON payload for the self-hosted model

        Returns:
            Dict: Created model information

        Raises:
            Exception: If the request fails
        """
        response = self._session.post(f"{self.url}/models", json=payload)
        if response.status_code in [200, 201]:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def create_self_hosted_embedded_model(self, payload: dict) -> dict:
        """Create a self-hosted embedding model configuration.

        Args:
            payload: JSON payload for the self-hosted embedding model

        Returns:
            Dict: Created model information

        Raises:
            Exception: If the request fails
        """
        response = self._session.post(f"{self.url}/models", json=payload)
        if response.status_code in [200, 201]:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def delete_model(self, model_id: str) -> bool:
        """Delete a model.

        Args:
            model_id: The ID of the model to delete

        Returns:
            bool: True if deletion was successful

        Raises:
            Exception: If the request fails
        """
        response = self._session.delete(f"{self.url}/models/{model_id}")
        if response.status_code in [200, 204]:
            return True
        else:
            raise parse_error(response.status_code, response)

    def get_model(self, model_id: str) -> dict:
        """Get details of a specific model.

        Args:
            model_id: The ID of the model to retrieve

        Returns:
            Dict: Model information

        Raises:
            Exception: If the request fails
        """
        models = self.list_models()
        for model in models:
            if model.get("modelId") == model_id:
                return model

        raise Exception(f"Model with ID {model_id} not found")
