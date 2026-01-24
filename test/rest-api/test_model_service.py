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

"""Unit tests for ModelService."""

import sys
from pathlib import Path
from unittest.mock import patch

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class TestModelService:
    """Test suite for ModelService class."""

    def test_list_models(self):
        """Test listing models by type."""
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1", "model2"]},
            ModelType.EMBEDDING: {"provider2": ["embed1"]},
        }

        service = ModelService(mock_cache)
        result = service.list_models([ModelType.TEXTGEN])

        assert result == {ModelType.TEXTGEN: {"provider1": ["model1", "model2"]}}

    def test_list_models_multiple_types(self):
        """Test listing multiple model types."""
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1"]},
            ModelType.EMBEDDING: {"provider2": ["embed1"]},
        }

        service = ModelService(mock_cache)
        result = service.list_models([ModelType.TEXTGEN, ModelType.EMBEDDING])

        assert len(result) == 2
        assert ModelType.TEXTGEN in result
        assert ModelType.EMBEDDING in result

    def test_list_models_openai_format(self):
        """Test listing models in OpenAI format."""
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1", "model2"]},
        }

        with patch("services.model_service.time.time", return_value=1234567890):
            service = ModelService(mock_cache)
            result = service.list_models_openai_format()

            assert result["object"] == "list"
            assert len(result["data"]) == 2
            assert result["data"][0]["id"] == "model1 (provider1)"
            assert result["data"][0]["owned_by"] == "LISA"
            assert result["data"][0]["created"] == 1234567890

    def test_get_model_metadata_success(self):
        """Test getting model metadata successfully."""
        from services.model_service import ModelService

        mock_cache = {
            "metadata": {
                "provider1.model1": {
                    "provider": "provider1",
                    "modelName": "model1",
                    "modelType": "textgen",
                }
            }
        }

        service = ModelService(mock_cache)
        result = service.get_model_metadata("provider1", "model1")

        assert result is not None
        assert result["provider"] == "provider1"
        assert result["modelName"] == "model1"

    def test_get_model_metadata_not_found(self):
        """Test getting metadata for non-existent model."""
        from services.model_service import ModelService

        mock_cache = {"metadata": {}}

        service = ModelService(mock_cache)
        result = service.get_model_metadata("unknown", "unknown")

        assert result is None

    def test_describe_models(self):
        """Test describing models with metadata."""
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1", "model2"]},
            "metadata": {
                "provider1.model1": {"name": "model1", "type": "textgen"},
                "provider1.model2": {"name": "model2", "type": "textgen"},
            },
        }

        service = ModelService(mock_cache)
        result = service.describe_models([ModelType.TEXTGEN])

        assert ModelType.TEXTGEN in result
        assert "provider1" in result[ModelType.TEXTGEN]
        assert len(result[ModelType.TEXTGEN]["provider1"]) == 2

    def test_describe_models_missing_metadata(self):
        """Test describing models when some metadata is missing."""
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1", "model2"]},
            "metadata": {
                "provider1.model1": {"name": "model1"},
                # model2 metadata is missing
            },
        }

        service = ModelService(mock_cache)
        result = service.describe_models([ModelType.TEXTGEN])

        # Should only include models with metadata
        assert len(result[ModelType.TEXTGEN]["provider1"]) == 1

    def test_list_models_empty_cache(self):
        """Test listing models with empty cache."""
        from services.model_service import ModelService
        from utils.resources import ModelType

        service = ModelService({})
        result = service.list_models([ModelType.TEXTGEN])

        assert result == {ModelType.TEXTGEN: {}}
