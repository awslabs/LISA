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

"""Unit tests for litellm_model_sync module."""

import os
import sys
from unittest.mock import MagicMock, patch

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials and required env vars before importing the module
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("MANAGEMENT_KEY_NAME", "test-key")
os.environ.setdefault("MODEL_TABLE_NAME", "test-models-table")
os.environ.setdefault("REST_API_CONTAINER_ENDPOINT_PS_NAME", "test-endpoint")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "test-guardrails-table")


# --- build_litellm_params tests ---


class TestBuildLitellmParams:
    """Tests for the build_litellm_params function."""

    def _import_build_litellm_params(self):
        from models.litellm_model_sync import build_litellm_params

        return build_litellm_params

    def test_non_managed_model_returns_model_name(self):
        """Non-managed model (no URL/ASG) should return just the model name with drop_params."""
        build = self._import_build_litellm_params()
        item = {
            "model_config": {"modelName": "bedrock/claude-v2", "modelType": "textgen"},
        }
        result = build(item)
        assert result == {"drop_params": True, "model": "bedrock/claude-v2"}

    def test_vllm_managed_model(self):
        """LISA-managed vLLM model should use hosted_vllm prefix and append /v1."""
        build = self._import_build_litellm_params()
        item = {
            "model_url": "http://my-endpoint:8080",
            "model_config": {
                "modelName": "my-model",
                "modelType": "textgen",
                "inferenceContainer": "vllm",
                "autoScalingConfig": {"minCapacity": 1},
            },
        }
        result = build(item)
        assert result["model"] == "hosted_vllm/my-model"
        assert result["api_base"] == "http://my-endpoint:8080/v1"
        assert result["drop_params"] is True

    def test_vllm_managed_model_url_already_has_v1(self):
        """If model_url already ends with /v1, don't double it."""
        build = self._import_build_litellm_params()
        item = {
            "model_url": "http://my-endpoint:8080/v1",
            "model_config": {
                "modelName": "my-model",
                "modelType": "textgen",
                "inferenceContainer": "vllm",
                "autoScalingConfig": {"minCapacity": 1},
            },
        }
        result = build(item)
        assert result["api_base"] == "http://my-endpoint:8080/v1"

    def test_openai_managed_model_strips_prefix(self):
        """Non-vLLM managed model with openai/ prefix should strip it to avoid duplication."""
        build = self._import_build_litellm_params()
        item = {
            "model_url": "http://my-endpoint:8080",
            "model_config": {
                "modelName": "openai/gpt-4",
                "modelType": "textgen",
                "inferenceContainer": "tgi",
                "autoScalingConfig": {"minCapacity": 1},
            },
        }
        result = build(item)
        assert result["model"] == "openai/gpt-4"

    def test_video_model_has_no_drop_params(self):
        """Video generation models should have empty litellm_params (no drop_params)."""
        build = self._import_build_litellm_params()
        item = {
            "model_config": {"modelName": "video-model", "modelType": "videogen"},
        }
        result = build(item)
        assert "drop_params" not in result
        assert result["model"] == "video-model"

    def test_empty_model_item(self):
        """Empty model item should return drop_params and empty model name."""
        build = self._import_build_litellm_params()
        result = build({})
        assert result == {"drop_params": True, "model": ""}


# --- sync_model_to_litellm tests ---


class TestSyncModelToLitellm:
    """Tests for the sync_model_to_litellm function."""

    def _import_sync(self):
        from models.litellm_model_sync import sync_model_to_litellm

        return sync_model_to_litellm

    def test_skips_existing_model(self):
        """Model already in LiteLLM should be skipped."""
        sync = self._import_sync()
        mock_client = MagicMock()
        mock_table = MagicMock()
        item = {"model_id": "existing-model", "model_config": {"modelName": "test"}}

        result = sync(mock_client, mock_table, item, {"existing-model"})

        assert result["status"] == "skipped"
        assert result["reason"] == "already_exists_in_litellm"
        mock_client.add_model.assert_not_called()

    @patch("models.litellm_model_sync.now", return_value="2025-01-01T00:00:00Z")
    def test_syncs_new_model_with_model_info_id(self, mock_now):
        """New model should be added and DDB updated with litellm_id from model_info."""
        sync = self._import_sync()
        mock_client = MagicMock()
        mock_client.add_model.return_value = {"model_info": {"id": "litellm-abc"}}
        mock_table = MagicMock()
        item = {"model_id": "new-model", "model_config": {"modelName": "test-model"}}

        result = sync(mock_client, mock_table, item, set())

        assert result["status"] == "synced"
        assert result["litellm_id"] == "litellm-abc"
        mock_table.update_item.assert_called_once()

    def test_syncs_new_model_with_top_level_id(self):
        """Should extract litellm_id from top-level 'id' field."""
        sync = self._import_sync()
        mock_client = MagicMock()
        mock_client.add_model.return_value = {"id": "litellm-xyz"}
        mock_table = MagicMock()
        item = {"model_id": "new-model", "model_config": {"modelName": "test"}}

        result = sync(mock_client, mock_table, item, set())

        assert result["litellm_id"] == "litellm-xyz"

    def test_syncs_new_model_with_model_id_field(self):
        """Should extract litellm_id from 'model_id' response field."""
        sync = self._import_sync()
        mock_client = MagicMock()
        mock_client.add_model.return_value = {"model_id": "litellm-123"}
        mock_table = MagicMock()
        item = {"model_id": "new-model", "model_config": {"modelName": "test"}}

        result = sync(mock_client, mock_table, item, set())

        assert result["litellm_id"] == "litellm-123"

    def test_handles_missing_litellm_id_in_response(self):
        """If response has no recognizable ID field, litellm_id should be None."""
        sync = self._import_sync()
        mock_client = MagicMock()
        mock_client.add_model.return_value = {"status": "ok"}
        mock_table = MagicMock()
        item = {"model_id": "new-model", "model_config": {"modelName": "test"}}

        result = sync(mock_client, mock_table, item, set())

        assert result["status"] == "synced"
        assert result["litellm_id"] is None
        mock_table.update_item.assert_not_called()

    def test_handles_add_model_exception(self):
        """Exception during add_model should return failed status."""
        sync = self._import_sync()
        mock_client = MagicMock()
        mock_client.add_model.side_effect = RuntimeError("connection refused")
        mock_table = MagicMock()
        item = {"model_id": "fail-model", "model_config": {"modelName": "test"}}

        result = sync(mock_client, mock_table, item, set())

        assert result["status"] == "failed"
        assert "connection refused" in result["error"]
