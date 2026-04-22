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

"""Unit tests for model_context_window_backfill Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials and required env vars
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["MODEL_TABLE_NAME"] = "model-table"
os.environ["GUARDRAILS_TABLE_NAME"] = "guardrails-table"
os.environ["MANAGEMENT_KEY_NAME"] = "test-management-key"
os.environ["MODELS_BUCKET_NAME"] = "test-models-bucket"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

# Patch utilities before importing the module
mock_common = MagicMock()
mock_common.get_cert_path.return_value = None
mock_common.get_rest_api_container_endpoint.return_value = "https://test-api.example.com"
mock_common.retry_config = retry_config

patch("utilities.common_functions.get_cert_path", mock_common.get_cert_path).start()
patch("utilities.common_functions.get_rest_api_container_endpoint", mock_common.get_rest_api_container_endpoint).start()
patch("utilities.common_functions.retry_config", retry_config).start()

# Mock boto3.client for import-time dependencies (secretsmanager used at module import)
mock_secrets = MagicMock()
mock_secrets.get_secret_value.return_value = {"SecretString": "test-secret"}


def mock_boto3_client(*args, **kwargs):
    service = args[0] if args else kwargs.get("service_name", kwargs.get("service"))
    if service == "secretsmanager":
        return mock_secrets
    elif service == "iam":
        return MagicMock()
    elif service == "s3":
        return MagicMock()
    else:
        return MagicMock()


patch("boto3.client", side_effect=mock_boto3_client).start()


class MockS3Exceptions:
    class NoSuchKey(Exception):
        pass


from models.model_context_window_backfill import (
    _fetch_context_window_from_litellm,
    _fetch_context_window_from_s3,
    _is_lisa_managed,
    _run_backfill,
    lambda_handler,
    PHYSICAL_RESOURCE_ID,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def model_table(dynamodb):
    """Create a mock DynamoDB model table."""
    table = dynamodb.create_table(
        TableName="model-table",
        KeySchema=[{"AttributeName": "model_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "model_id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


# ============================================================================
# Tests for _is_lisa_managed helper
# ============================================================================


def test_is_lisa_managed_true():
    """Test _is_lisa_managed returns True when all ECS hosting fields are present."""
    item = {
        "model_config": {
            "autoScalingConfig": {"minCapacity": 1},
            "containerConfig": {"image": {"baseImage": "test"}},
            "inferenceContainer": "vllm",
            "instanceType": "t3.medium",
            "loadBalancerConfig": {"healthCheckConfig": {}},
        }
    }
    assert _is_lisa_managed(item) is True


def test_is_lisa_managed_false():
    """Test _is_lisa_managed returns False for external/Bedrock models."""
    item = {"model_config": {"modelName": "bedrock/claude-v2", "modelType": "textgen"}}
    assert _is_lisa_managed(item) is False


def test_is_lisa_managed_empty():
    """Test _is_lisa_managed returns False with empty item."""
    assert _is_lisa_managed({}) is False


# ============================================================================
# Tests for _fetch_context_window_from_litellm helper
# ============================================================================


def test_fetch_from_litellm_with_id():
    """Test fetching context window via get_model when litellm_id is present."""
    mock_client = MagicMock()
    mock_client.get_model.return_value = {
        "model_info": {"id": "abc", "max_input_tokens": 200000},
    }
    result = _fetch_context_window_from_litellm(mock_client, "abc", "model-id")
    assert result == 200000
    mock_client.get_model.assert_called_once_with("abc")


def test_fetch_from_litellm_fallback_on_missing_id():
    """Test falling back to list_models when litellm_id is None."""
    mock_client = MagicMock()
    mock_client.list_models.return_value = [
        {"model_name": "model-id", "model_info": {"max_input_tokens": 100000}},
    ]
    result = _fetch_context_window_from_litellm(mock_client, None, "model-id")
    assert result == 100000
    mock_client.get_model.assert_not_called()


def test_fetch_from_litellm_fallback_on_get_model_error():
    """Test falling back to list_models when get_model raises."""
    mock_client = MagicMock()
    mock_client.get_model.side_effect = Exception("Not found")
    mock_client.list_models.return_value = [
        {"model_name": "model-id", "model_info": {"max_input_tokens": 128000}},
    ]
    result = _fetch_context_window_from_litellm(mock_client, "bad-id", "model-id")
    assert result == 128000


def test_fetch_from_litellm_all_fail_returns_none():
    """Test that None is returned when both get_model and list_models fail."""
    mock_client = MagicMock()
    mock_client.get_model.side_effect = Exception("err1")
    mock_client.list_models.side_effect = Exception("err2")
    result = _fetch_context_window_from_litellm(mock_client, "bad-id", "model-id")
    assert result is None


def test_fetch_from_litellm_no_match_in_list():
    """Test that None is returned when list_models has no matching model."""
    mock_client = MagicMock()
    mock_client.list_models.return_value = [
        {"model_name": "other-model", "model_info": {"max_input_tokens": 50000}},
    ]
    result = _fetch_context_window_from_litellm(mock_client, None, "model-id")
    assert result is None


# ============================================================================
# Tests for _fetch_context_window_from_s3 helper
# ============================================================================


def test_fetch_from_s3_success():
    """Test reading max_position_embeddings from config.json."""
    mock_s3 = MagicMock()
    mock_s3.exceptions = MockS3Exceptions()
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps({"max_position_embeddings": 32768}).encode())
    }
    result = _fetch_context_window_from_s3(mock_s3, "bucket", "mistralai/Mistral-7B", "textgen")
    assert result == 32768
    mock_s3.get_object.assert_called_with(Bucket="bucket", Key="mistralai/Mistral-7B/config.json")


def test_fetch_from_s3_imagegen_fallback():
    """Test that IMAGEGEN models fall back to text_encoder/config.json."""
    mock_s3 = MagicMock()
    mock_s3.exceptions = MockS3Exceptions()
    mock_s3.get_object.side_effect = [
        MockS3Exceptions.NoSuchKey("not found"),
        {"Body": MagicMock(read=lambda: json.dumps({"max_position_embeddings": 77}).encode())},
    ]
    result = _fetch_context_window_from_s3(mock_s3, "bucket", "sd/v1", "imagegen")
    assert result == 77
    assert mock_s3.get_object.call_count == 2


def test_fetch_from_s3_no_key_returns_none():
    """Test that None is returned when config.json does not exist in S3."""
    mock_s3 = MagicMock()
    mock_s3.exceptions = MockS3Exceptions()
    mock_s3.get_object.side_effect = MockS3Exceptions.NoSuchKey("not found")
    result = _fetch_context_window_from_s3(mock_s3, "bucket", "nonexistent", "textgen")
    assert result is None


def test_fetch_from_s3_missing_key_returns_none():
    """Test that None is returned when config.json lacks max_position_embeddings."""
    mock_s3 = MagicMock()
    mock_s3.exceptions = MockS3Exceptions()
    mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: json.dumps({"hidden_size": 4096}).encode())}
    result = _fetch_context_window_from_s3(mock_s3, "bucket", "model", "textgen")
    assert result is None


# ============================================================================
# Tests for _run_backfill
# ============================================================================


def test_run_backfill_enriches_bedrock_model(model_table):
    """Test that a non-LISA-managed Bedrock model is enriched via LiteLLM."""
    model_table.put_item(
        Item={
            "model_id": "bedrock-model",
            "model_status": "InService",
            "litellm_id": "litellm-abc",
            "model_config": {"modelName": "bedrock/claude-v2", "modelType": "textgen"},
        }
    )

    mock_litellm = MagicMock()
    mock_litellm.get_model.return_value = {
        "model_info": {"id": "litellm-abc", "max_input_tokens": 200000},
    }

    with (
        patch("models.model_context_window_backfill._get_litellm_client", return_value=mock_litellm),
        patch("models.model_context_window_backfill.boto3") as mock_boto,
        patch("models.model_context_window_backfill.now", return_value=123456),
    ):
        mock_boto.resource.return_value.Table.return_value = model_table
        mock_boto.client.return_value = MagicMock()
        result = _run_backfill()

    assert result["enriched"] == "1"
    assert result["skipped"] == "0"
    assert result["failed"] == "0"

    item = model_table.get_item(Key={"model_id": "bedrock-model"})["Item"]
    assert item["context_window"] == 200000


def test_run_backfill_skips_already_enriched(model_table):
    """Test that models with an existing context_window are skipped."""
    model_table.put_item(
        Item={
            "model_id": "enriched-model",
            "model_status": "InService",
            "context_window": 50000,
            "model_config": {"modelName": "test", "modelType": "textgen"},
        }
    )

    mock_litellm = MagicMock()

    with (
        patch("models.model_context_window_backfill._get_litellm_client", return_value=mock_litellm),
        patch("models.model_context_window_backfill.boto3") as mock_boto,
    ):
        mock_boto.resource.return_value.Table.return_value = model_table
        mock_boto.client.return_value = MagicMock()
        result = _run_backfill()

    assert result["enriched"] == "0"
    assert result["skipped"] == "1"
    assert result["failed"] == "0"

    # Value must remain unchanged
    item = model_table.get_item(Key={"model_id": "enriched-model"})["Item"]
    assert item["context_window"] == 50000


def test_run_backfill_defaults_to_zero_when_not_found(model_table):
    """Test that models where context window cannot be determined default to 0."""
    model_table.put_item(
        Item={
            "model_id": "unknown-model",
            "model_status": "InService",
            "model_config": {"modelName": "mystery", "modelType": "textgen"},
        }
    )

    mock_litellm = MagicMock()
    mock_litellm.get_model.side_effect = Exception("Not found")
    mock_litellm.list_models.return_value = []

    with (
        patch("models.model_context_window_backfill._get_litellm_client", return_value=mock_litellm),
        patch("models.model_context_window_backfill.boto3") as mock_boto,
        patch("models.model_context_window_backfill.now", return_value=123456),
    ):
        mock_boto.resource.return_value.Table.return_value = model_table
        mock_boto.client.return_value = MagicMock()
        result = _run_backfill()

    assert result["enriched"] == "1"
    item = model_table.get_item(Key={"model_id": "unknown-model"})["Item"]
    assert item["context_window"] == 0


def test_run_backfill_counts_failures(model_table):
    """Test that exceptions during individual model processing increment failed count."""
    model_table.put_item(
        Item={
            "model_id": "error-model",
            "model_status": "InService",
            "litellm_id": "some-id",
            "model_config": {"modelName": "error-model", "modelType": "textgen"},
        }
    )

    with (
        patch("models.model_context_window_backfill._get_litellm_client", return_value=MagicMock()),
        patch(
            "models.model_context_window_backfill._fetch_context_window_from_litellm",
            side_effect=RuntimeError("Unexpected crash"),
        ),
        patch("models.model_context_window_backfill.boto3") as mock_boto,
    ):
        mock_boto.resource.return_value.Table.return_value = model_table
        mock_boto.client.return_value = MagicMock()
        result = _run_backfill()

    assert result["failed"] == "1"
    assert result["enriched"] == "0"


def test_run_backfill_empty_table(model_table):
    """Test backfill on an empty table returns all zeros."""
    with (
        patch("models.model_context_window_backfill._get_litellm_client", return_value=MagicMock()),
        patch("models.model_context_window_backfill.boto3") as mock_boto,
    ):
        mock_boto.resource.return_value.Table.return_value = model_table
        mock_boto.client.return_value = MagicMock()
        result = _run_backfill()

    assert result == {"enriched": "0", "skipped": "0", "failed": "0"}


# ============================================================================
# Tests for lambda_handler
# ============================================================================


def test_lambda_handler_create_success():
    """Test that RequestType=Create runs the backfill and returns SUCCESS."""
    event = {"RequestType": "Create"}

    mock_data = {"enriched": "5", "skipped": "2", "failed": "0"}
    with patch("models.model_context_window_backfill._run_backfill", return_value=mock_data):
        result = lambda_handler(event, None)

    assert result["Status"] == "SUCCESS"
    assert result["PhysicalResourceId"] == PHYSICAL_RESOURCE_ID
    assert result["Data"] == mock_data


def test_lambda_handler_update_is_noop():
    """Test that RequestType=Update returns SUCCESS without running the backfill."""
    event = {"RequestType": "Update"}

    with patch("models.model_context_window_backfill._run_backfill") as mock_backfill:
        result = lambda_handler(event, None)

    assert result["Status"] == "SUCCESS"
    assert result["PhysicalResourceId"] == PHYSICAL_RESOURCE_ID
    mock_backfill.assert_not_called()


def test_lambda_handler_delete_is_noop():
    """Test that RequestType=Delete returns SUCCESS without running the backfill."""
    event = {"RequestType": "Delete"}

    with patch("models.model_context_window_backfill._run_backfill") as mock_backfill:
        result = lambda_handler(event, None)

    assert result["Status"] == "SUCCESS"
    assert result["PhysicalResourceId"] == PHYSICAL_RESOURCE_ID
    mock_backfill.assert_not_called()


def test_lambda_handler_create_failure():
    """Test that exceptions during backfill result in FAILED status."""
    event = {"RequestType": "Create"}

    with patch("models.model_context_window_backfill._run_backfill", side_effect=RuntimeError("DynamoDB is down")):
        result = lambda_handler(event, None)

    assert result["Status"] == "FAILED"
    assert result["PhysicalResourceId"] == PHYSICAL_RESOURCE_ID
    assert "DynamoDB is down" in result["Reason"]


def test_lambda_handler_physical_resource_id_is_static():
    """Test that the PhysicalResourceId is always the same static string."""
    with patch("models.model_context_window_backfill._run_backfill", return_value={}):
        create_result = lambda_handler({"RequestType": "Create"}, None)
    update_result = lambda_handler({"RequestType": "Update"}, None)
    delete_result = lambda_handler({"RequestType": "Delete"}, None)

    assert create_result["PhysicalResourceId"] == PHYSICAL_RESOURCE_ID
    assert update_result["PhysicalResourceId"] == PHYSICAL_RESOURCE_ID
    assert delete_result["PhysicalResourceId"] == PHYSICAL_RESOURCE_ID
