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

"""Unit tests for ModelMixin."""


import pytest
import responses
from lisapy import LisaApi


class TestModelMixin:
    """Test suite for model-related operations."""

    @responses.activate
    def test_list_models(self, lisa_api: LisaApi, api_url: str, mock_models_response: dict):
        """Test listing all models."""
        responses.add(responses.GET, f"{api_url}/models", json=mock_models_response, status=200)

        models = lisa_api.list_models()

        assert len(models) == 3
        assert models[0]["modelId"] == "anthropic.claude-v2"
        assert models[1]["modelType"] == "embedding"
        assert models[2]["provider"] == "ecs.textgen.tgi"

    @responses.activate
    def test_list_embedding_models(self, lisa_api: LisaApi, api_url: str, mock_models_response: dict):
        """Test listing only embedding models."""
        responses.add(responses.GET, f"{api_url}/models", json=mock_models_response, status=200)

        embeddings = lisa_api.list_embedding_models()

        assert len(embeddings) == 1
        assert embeddings[0]["modelId"] == "amazon.titan-embed-text-v1"
        assert embeddings[0]["modelType"] == "embedding"

    @responses.activate
    def test_list_instances(self, lisa_api: LisaApi, api_url: str, mock_instances_response: list):
        """Test listing available instance types."""
        responses.add(responses.GET, f"{api_url}/models/metadata/instances", json=mock_instances_response, status=200)

        instances = lisa_api.list_instances()

        assert len(instances) == 5
        assert "ml.g5.xlarge" in instances
        assert "ml.p4d.24xlarge" in instances

    @responses.activate
    def test_create_bedrock_model(self, lisa_api: LisaApi, api_url: str):
        """Test creating a Bedrock model."""
        payload = {
            "modelId": "anthropic.claude-v3",
            "modelName": "Claude v3",
            "modelType": "textgen",
            "provider": "bedrock",
        }
        expected_response = {**payload, "status": "ACTIVE", "createdAt": "2024-01-24T10:00:00Z"}

        responses.add(responses.POST, f"{api_url}/models", json=expected_response, status=201)

        result = lisa_api.create_bedrock_model(payload)

        assert result["modelId"] == "anthropic.claude-v3"
        assert result["status"] == "ACTIVE"
        assert len(responses.calls) == 1
        assert responses.calls[0].request.body is not None

    @responses.activate
    def test_create_self_hosted_model(self, lisa_api: LisaApi, api_url: str):
        """Test creating a self-hosted model."""
        payload = {
            "modelId": "custom-llama-3",
            "modelName": "Llama 3 8B",
            "modelType": "textgen",
            "provider": "ecs.textgen.tgi",
            "instanceType": "ml.g5.2xlarge",
        }
        expected_response = {**payload, "status": "CREATING", "createdAt": "2024-01-24T11:00:00Z"}

        responses.add(responses.POST, f"{api_url}/models", json=expected_response, status=201)

        result = lisa_api.create_self_hosted_model(payload)

        assert result["modelId"] == "custom-llama-3"
        assert result["status"] == "CREATING"

    @responses.activate
    def test_create_self_hosted_embedded_model(self, lisa_api: LisaApi, api_url: str):
        """Test creating a self-hosted embedding model."""
        payload = {
            "modelId": "custom-embeddings",
            "modelName": "Custom Embeddings",
            "modelType": "embedding",
            "provider": "ecs.embedding.instructor",
            "instanceType": "ml.g5.xlarge",
        }
        expected_response = {**payload, "status": "CREATING", "createdAt": "2024-01-24T12:00:00Z"}

        responses.add(responses.POST, f"{api_url}/models", json=expected_response, status=201)

        result = lisa_api.create_self_hosted_embedded_model(payload)

        assert result["modelId"] == "custom-embeddings"
        assert result["modelType"] == "embedding"

    @responses.activate
    def test_delete_model(self, lisa_api: LisaApi, api_url: str):
        """Test deleting a model."""
        model_id = "custom-llama-2"
        responses.add(responses.DELETE, f"{api_url}/models/{model_id}", status=204)

        result = lisa_api.delete_model(model_id)

        assert result is True
        assert len(responses.calls) == 1

    @responses.activate
    def test_get_model(self, lisa_api: LisaApi, api_url: str, mock_models_response: dict):
        """Test getting a specific model by ID."""
        responses.add(responses.GET, f"{api_url}/models", json=mock_models_response, status=200)

        model = lisa_api.get_model("anthropic.claude-v2")

        assert model["modelId"] == "anthropic.claude-v2"
        assert model["modelName"] == "Claude v2"

    @responses.activate
    def test_get_model_not_found(self, lisa_api: LisaApi, api_url: str, mock_models_response: dict):
        """Test getting a model that doesn't exist."""
        responses.add(responses.GET, f"{api_url}/models", json=mock_models_response, status=200)

        with pytest.raises(Exception, match="Model with ID .* not found"):
            lisa_api.get_model("non-existent-model")

    @responses.activate
    def test_list_models_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when listing models fails."""
        responses.add(responses.GET, f"{api_url}/models", json={"error": "Internal error"}, status=500)

        with pytest.raises(Exception):
            lisa_api.list_models()
