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

"""Tests for model registration service."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the REST API source to the path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class MockRegistry:
    """Mock registry for testing."""

    def get_assets(self, provider: str):
        """Mock get_assets method."""
        mock_validator_instance = MagicMock()
        mock_validator_instance.dict.return_value = {"temperature": 0.7, "max_tokens": 100}
        mock_validator = MagicMock(return_value=mock_validator_instance)

        return {
            "adapter": MagicMock(),
            "validator": mock_validator,
        }


class TestModelRegistrationService:
    """Tests for ModelRegistrationService."""

    def test_create_empty_cache(self):
        """Test creating empty cache structure."""
        from services.model_registration import ModelRegistrationService
        from utils.resources import ModelType, RestApiResource

        service = ModelRegistrationService(MockRegistry())
        cache = service.create_empty_cache()

        assert ModelType.EMBEDDING in cache
        assert ModelType.TEXTGEN in cache
        assert RestApiResource.EMBEDDINGS in cache
        assert RestApiResource.GENERATE in cache
        assert RestApiResource.GENERATE_STREAM in cache
        assert "metadata" in cache
        assert "endpointUrls" in cache

    def test_is_supported_container(self):
        """Test checking supported containers."""
        from services.model_registration import ModelRegistrationService

        service = ModelRegistrationService(MockRegistry())

        assert service.is_supported_container("tgi") is True
        assert service.is_supported_container("tei") is True
        assert service.is_supported_container("instructor") is True
        assert service.is_supported_container("unsupported") is False

    def test_register_textgen_model(self):
        """Test registering a text generation model."""
        from services.model_registration import ModelRegistrationService
        from utils.resources import ModelType, RestApiResource

        service = ModelRegistrationService(MockRegistry())
        cache = service.create_empty_cache()

        model = {
            "provider": "ecs.textgen.tgi",
            "modelName": "test-model",
            "modelType": ModelType.TEXTGEN,
            "endpointUrl": "http://test-endpoint",
            "streaming": True,
        }

        service.register_model(model, cache)

        # Check endpoint URL
        assert cache["endpointUrls"]["ecs.textgen.tgi.test-model"] == "http://test-endpoint"

        # Check metadata
        assert "ecs.textgen.tgi.test-model" in cache["metadata"]
        metadata = cache["metadata"]["ecs.textgen.tgi.test-model"]
        assert metadata["provider"] == "ecs.textgen.tgi"
        assert metadata["modelName"] == "test-model"
        assert metadata["modelType"] == ModelType.TEXTGEN
        assert metadata["streaming"] is True

        # Check registration by type and resource
        assert "ecs.textgen.tgi" in cache[ModelType.TEXTGEN]
        assert "test-model" in cache[ModelType.TEXTGEN]["ecs.textgen.tgi"]
        assert "ecs.textgen.tgi" in cache[RestApiResource.GENERATE]
        assert "test-model" in cache[RestApiResource.GENERATE]["ecs.textgen.tgi"]
        assert "ecs.textgen.tgi" in cache[RestApiResource.GENERATE_STREAM]
        assert "test-model" in cache[RestApiResource.GENERATE_STREAM]["ecs.textgen.tgi"]

    def test_register_embedding_model(self):
        """Test registering an embedding model."""
        from services.model_registration import ModelRegistrationService
        from utils.resources import ModelType, RestApiResource

        service = ModelRegistrationService(MockRegistry())
        cache = service.create_empty_cache()

        model = {
            "provider": "ecs.embedding.tei",
            "modelName": "embed-model",
            "modelType": ModelType.EMBEDDING,
            "endpointUrl": "http://embed-endpoint",
        }

        service.register_model(model, cache)

        # Check registration
        assert "ecs.embedding.tei" in cache[ModelType.EMBEDDING]
        assert "embed-model" in cache[ModelType.EMBEDDING]["ecs.embedding.tei"]
        assert "ecs.embedding.tei" in cache[RestApiResource.EMBEDDINGS]
        assert "embed-model" in cache[RestApiResource.EMBEDDINGS]["ecs.embedding.tei"]

        # Should not be in GENERATE_STREAM
        assert "ecs.embedding.tei" not in cache[RestApiResource.GENERATE_STREAM]

    def test_register_textgen_model_without_streaming(self):
        """Test registering a text generation model without streaming."""
        from services.model_registration import ModelRegistrationService
        from utils.resources import ModelType, RestApiResource

        service = ModelRegistrationService(MockRegistry())
        cache = service.create_empty_cache()

        model = {
            "provider": "ecs.textgen.tgi",
            "modelName": "test-model",
            "modelType": ModelType.TEXTGEN,
            "endpointUrl": "http://test-endpoint",
            "streaming": False,
        }

        service.register_model(model, cache)

        # Should be in GENERATE but not GENERATE_STREAM
        assert "ecs.textgen.tgi" in cache[RestApiResource.GENERATE]
        assert "ecs.textgen.tgi" not in cache[RestApiResource.GENERATE_STREAM]

    def test_register_model_skips_unsupported_container(self):
        """Test that unsupported containers are skipped."""
        from services.model_registration import ModelRegistrationService

        service = ModelRegistrationService(MockRegistry())
        cache = service.create_empty_cache()

        model = {
            "provider": "ecs.textgen.unsupported",
            "modelName": "test-model",
            "modelType": "textgen",
            "endpointUrl": "http://test-endpoint",
        }

        service.register_model(model, cache)

        # Should not be registered
        assert "ecs.textgen.unsupported.test-model" not in cache["endpointUrls"]
        assert "ecs.textgen.unsupported.test-model" not in cache["metadata"]

    def test_register_model_invalid_provider_format(self):
        """Test that invalid provider format is skipped."""
        from services.model_registration import ModelRegistrationService

        service = ModelRegistrationService(MockRegistry())
        cache = service.create_empty_cache()

        model = {
            "provider": "invalid-format",
            "modelName": "test-model",
            "modelType": "textgen",
            "endpointUrl": "http://test-endpoint",
        }

        service.register_model(model, cache)

        # Should not be registered
        assert "invalid-format.test-model" not in cache["endpointUrls"]

    def test_register_models_multiple(self):
        """Test registering multiple models."""
        from services.model_registration import ModelRegistrationService
        from utils.resources import ModelType

        service = ModelRegistrationService(MockRegistry())

        models = [
            {
                "provider": "ecs.textgen.tgi",
                "modelName": "model1",
                "modelType": ModelType.TEXTGEN,
                "endpointUrl": "http://endpoint1",
                "streaming": True,
            },
            {
                "provider": "ecs.embedding.tei",
                "modelName": "model2",
                "modelType": ModelType.EMBEDDING,
                "endpointUrl": "http://endpoint2",
            },
        ]

        cache = service.register_models(models)

        assert "ecs.textgen.tgi.model1" in cache["endpointUrls"]
        assert "ecs.embedding.tei.model2" in cache["endpointUrls"]

    def test_register_models_continues_on_error(self):
        """Test that registration continues even if one model fails."""
        from services.model_registration import ModelRegistrationService
        from utils.resources import ModelType

        # Create a registry that raises an error for one provider
        class ErrorRegistry:
            def get_assets(self, provider: str):
                if provider == "ecs.textgen.tgi":
                    raise Exception("Test error")
                mock_validator_instance = MagicMock()
                mock_validator_instance.dict.return_value = {}
                return {"adapter": MagicMock(), "validator": MagicMock(return_value=mock_validator_instance)}

        service = ModelRegistrationService(ErrorRegistry())

        models = [
            {
                "provider": "ecs.textgen.tgi",
                "modelName": "bad-model",
                "modelType": ModelType.TEXTGEN,
                "endpointUrl": "http://endpoint1",
            },
            {
                "provider": "ecs.embedding.tei",
                "modelName": "good-model",
                "modelType": ModelType.EMBEDDING,
                "endpointUrl": "http://endpoint2",
            },
        ]

        cache = service.register_models(models)

        # Bad model should not be registered
        assert "ecs.textgen.tgi.bad-model" not in cache["endpointUrls"]
        # Good model should be registered
        assert "ecs.embedding.tei.good-model" in cache["endpointUrls"]
