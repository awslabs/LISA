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

import os
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

# Prevent lambda/models imports from failing during autouse fixtures.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("MODEL_TABLE_NAME", "model-table")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "guardrails-table")

from lisa.session.model_config import (  # noqa: E402
    get_current_model_config,
    update_session_with_current_model_config,
)
from lisa.session.models import (  # noqa: E402
    SelectedModel,
    SelectedModelFeature,
    SessionConfigurationModel,
)

# --- get_current_model_config ---


def test_get_current_model_config_returns_empty_when_no_table():
    assert get_current_model_config(None, "any-model") == {}


def test_get_current_model_config_returns_empty_when_no_model_id():
    table = MagicMock()
    assert get_current_model_config(table, "") == {}
    table.get_item.assert_not_called()


def test_get_current_model_config_extracts_model_config_field():
    table = MagicMock()
    table.get_item.return_value = {"Item": {"model_id": "m1", "model_config": {"streaming": True, "modelType": "tg"}}}
    result = get_current_model_config(table, "m1")
    assert result == {"streaming": True, "modelType": "tg"}
    table.get_item.assert_called_once_with(Key={"model_id": "m1"})


def test_get_current_model_config_returns_empty_when_no_item():
    table = MagicMock()
    table.get_item.return_value = {}
    assert get_current_model_config(table, "missing") == {}


def test_get_current_model_config_returns_empty_when_model_config_absent():
    table = MagicMock()
    table.get_item.return_value = {"Item": {"model_id": "m1"}}  # no model_config key
    assert get_current_model_config(table, "m1") == {}


def test_get_current_model_config_swallows_client_error():
    table = MagicMock()
    table.get_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}},
        operation_name="GetItem",
    )
    assert get_current_model_config(table, "m1") == {}


# --- update_session_with_current_model_config ---


def test_update_session_returns_unchanged_when_no_session_config():
    # Empty/none session_config short-circuits
    assert update_session_with_current_model_config(None, MagicMock()) is None  # type: ignore[arg-type]


def test_update_session_returns_unchanged_when_no_selected_model():
    cfg = SessionConfigurationModel()  # selectedModel default is None
    result = update_session_with_current_model_config(cfg, MagicMock())
    assert result is cfg


def test_update_session_returns_unchanged_when_no_model_id():
    cfg = SessionConfigurationModel(selectedModel=SelectedModel(modelName="anonymous"))
    table = MagicMock()
    result = update_session_with_current_model_config(cfg, table)
    assert result.selectedModel.modelName == "anonymous"
    table.get_item.assert_not_called()


def test_update_session_returns_unchanged_when_lookup_returns_empty():
    cfg = SessionConfigurationModel(selectedModel=SelectedModel(modelId="missing"))
    table = MagicMock()
    table.get_item.return_value = {"Item": {}}  # no model_config
    result = update_session_with_current_model_config(cfg, table)
    # Original modelId preserved, no other fields changed
    assert result.selectedModel.modelId == "missing"


def test_update_session_applies_all_supported_overrides():
    cfg = SessionConfigurationModel(
        selectedModel=SelectedModel(
            modelId="m1",
            modelName="orig-name",
            streaming=True,
            modelType="textgen",
            features=[SelectedModelFeature(name="old-feature")],
        )
    )
    table = MagicMock()
    table.get_item.return_value = {
        "Item": {
            "model_config": {
                "features": [{"name": "new-feature", "overview": ""}],
                "streaming": False,
                "modelType": "embedding",
                "modelDescription": "Updated",
                "allowedGroups": ["g1"],
            }
        }
    }
    result = update_session_with_current_model_config(cfg, table)
    sm = result.selectedModel
    assert sm.modelId == "m1"
    # modelName is NOT in the override list — must stay
    assert sm.modelName == "orig-name"
    assert sm.streaming is False
    assert sm.modelType == "embedding"
    assert sm.modelDescription == "Updated"
    assert sm.allowedGroups == ["g1"]
    assert len(sm.features) == 1
    assert sm.features[0].name == "new-feature"


def test_update_session_features_handles_already_validated_objects():
    """If a caller passes pre-built SelectedModelFeature objects, don't re-validate."""
    cfg = SessionConfigurationModel(selectedModel=SelectedModel(modelId="m1"))
    table = MagicMock()
    pre_built = SelectedModelFeature(name="pre-built")
    table.get_item.return_value = {"Item": {"model_config": {"features": [pre_built]}}}
    result = update_session_with_current_model_config(cfg, table)
    assert result.selectedModel.features[0].name == "pre-built"


def test_update_session_only_updates_present_fields():
    """Fields absent from current_model_config must not clobber existing values."""
    cfg = SessionConfigurationModel(
        selectedModel=SelectedModel(
            modelId="m1",
            streaming=True,
            modelType="textgen",
            modelDescription="orig-desc",
        )
    )
    table = MagicMock()
    # Only streaming is in the override
    table.get_item.return_value = {"Item": {"model_config": {"streaming": False}}}
    result = update_session_with_current_model_config(cfg, table)
    sm = result.selectedModel
    assert sm.streaming is False
    # Untouched
    assert sm.modelType == "textgen"
    assert sm.modelDescription == "orig-desc"


def test_update_session_does_not_mutate_input():
    """The original config must remain unchanged; a new copy is returned."""
    original = SessionConfigurationModel(
        selectedModel=SelectedModel(modelId="m1", streaming=True),
    )
    table = MagicMock()
    table.get_item.return_value = {"Item": {"model_config": {"streaming": False}}}
    update_session_with_current_model_config(original, table)
    assert original.selectedModel.streaming is True
