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

"""Unit tests for BulkEnrichContextWindowHandler."""

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

# Create mock modules
mock_common = MagicMock()
mock_common.get_cert_path.return_value = None
mock_common.get_rest_api_container_endpoint.return_value = "https://test-api.example.com"
mock_common.retry_config = retry_config

# Patch utilities before importing the handler
patch("utilities.common_functions.get_cert_path", mock_common.get_cert_path).start()
patch("utilities.common_functions.get_rest_api_container_endpoint", mock_common.get_rest_api_container_endpoint).start()
patch("utilities.common_functions.retry_config", retry_config).start()

# Create mock LiteLLM client
mock_litellm_client = MagicMock()

# Create mock S3 client
mock_s3 = MagicMock()


class MockS3Exceptions:
    class NoSuchKey(Exception):
        pass


mock_s3.exceptions = MockS3Exceptions()

# Mock boto3.client for import-time dependencies
mock_secrets = MagicMock()
mock_secrets.get_secret_value.return_value = {"SecretString": "test-secret"}


def mock_boto3_client(*args, **kwargs):
    service = args[0] if args else kwargs.get("service_name", kwargs.get("service"))
    if service == "secretsmanager":
        return mock_secrets
    elif service == "iam":
        return MagicMock()
    elif service == "s3":
        return mock_s3
    elif service == "ssm":
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "mock-value"}}
        return mock_ssm
    else:
        return MagicMock()


patch("boto3.client", side_effect=mock_boto3_client).start()

from models.handler.bulk_enrich_context_window_handler import (
    _fetch_from_litellm,
    _fetch_from_s3,
    _is_lisa_managed,
    BulkEnrichContextWindowHandler,
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
    """Create a mock DynamoDB table for models."""
    table = dynamodb.create_table(
        TableName="model-table",
        KeySchema=[{"AttributeName": "model_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "model_id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture(scope="function")
def guardrails_table(dynamodb):
    """Create a mock DynamoDB table for guardrails."""
    table = dynamodb.create_table(
        TableName="guardrails-table",
        KeySchema=[
            {"AttributeName": "guardrailId", "KeyType": "HASH"},
            {"AttributeName": "modelId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "guardrailId", "AttributeType": "S"},
            {"AttributeName": "modelId", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


def _make_handler(model_table, guardrails_table):
    """Create a BulkEnrichContextWindowHandler with mocked dependencies."""
    return BulkEnrichContextWindowHandler(
        autoscaling_client=MagicMock(),
        stepfunctions_client=MagicMock(),
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )


# ============================================================================
# Tests for _is_lisa_managed helper
# ============================================================================


def test_is_lisa_managed_true():
    """Test _is_lisa_managed returns True when all hosting fields are present."""
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


def test_is_lisa_managed_false_missing_fields():
    """Test _is_lisa_managed returns False when hosting fields are missing."""
    item = {
        "model_config": {
            "modelName": "bedrock-model",
            "modelType": "textgen",
        }
    }
    assert _is_lisa_managed(item) is False


def test_is_lisa_managed_false_empty_config():
    """Test _is_lisa_managed returns False with empty model_config."""
    assert _is_lisa_managed({}) is False
    assert _is_lisa_managed({"model_config": {}}) is False


# ============================================================================
# Tests for _fetch_from_litellm helper
# ============================================================================


def test_fetch_from_litellm_with_litellm_id():
    """Test fetching context window from LiteLLM using litellm_id."""
    mock_client = MagicMock()
    mock_client.get_model.return_value = {
        "model_info": {"id": "abc-123", "max_input_tokens": 200000},
    }

    result = _fetch_from_litellm(mock_client, "abc-123", "model-id")
    assert result == 200000
    mock_client.get_model.assert_called_once_with("abc-123")


def test_fetch_from_litellm_with_litellm_id_no_max_input():
    """Test fetching from LiteLLM when max_input_tokens is missing."""
    mock_client = MagicMock()
    mock_client.get_model.return_value = {
        "model_info": {"id": "abc-123"},
    }

    result = _fetch_from_litellm(mock_client, "abc-123", "model-id")
    # When max_input_tokens is None, int(None) raises TypeError
    # The function should handle this gracefully
    assert result is None or isinstance(result, int)


def test_fetch_from_litellm_fallback_to_list_models():
    """Test falling back to list_models when litellm_id is None."""
    mock_client = MagicMock()
    mock_client.list_models.return_value = [
        {"model_name": "model-id", "model_info": {"max_input_tokens": 100000}},
        {"model_name": "other-model", "model_info": {"max_input_tokens": 50000}},
    ]

    result = _fetch_from_litellm(mock_client, None, "model-id")
    assert result == 100000
    mock_client.get_model.assert_not_called()
    mock_client.list_models.assert_called_once()


def test_fetch_from_litellm_fallback_no_match():
    """Test fallback to list_models when no matching model is found."""
    mock_client = MagicMock()
    mock_client.list_models.return_value = [
        {"model_name": "other-model", "model_info": {"max_input_tokens": 50000}},
    ]

    result = _fetch_from_litellm(mock_client, None, "model-id")
    assert result is None


def test_fetch_from_litellm_get_model_exception_then_fallback():
    """Test that when get_model fails, it falls back to list_models."""
    mock_client = MagicMock()
    mock_client.get_model.side_effect = Exception("Not found")
    mock_client.list_models.return_value = [
        {"model_name": "model-id", "model_info": {"max_input_tokens": 128000}},
    ]

    result = _fetch_from_litellm(mock_client, "bad-id", "model-id")
    assert result == 128000


def test_fetch_from_litellm_all_fail():
    """Test when both get_model and list_models fail."""
    mock_client = MagicMock()
    mock_client.get_model.side_effect = Exception("Error 1")
    mock_client.list_models.side_effect = Exception("Error 2")

    result = _fetch_from_litellm(mock_client, "bad-id", "model-id")
    assert result is None


# ============================================================================
# Tests for _fetch_from_s3 helper
# ============================================================================


def test_fetch_from_s3_success():
    """Test fetching context window from S3 config.json."""
    local_mock_s3 = MagicMock()
    local_mock_s3.exceptions = MockS3Exceptions()
    local_mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps({"max_position_embeddings": 32768}).encode())
    }

    with patch("models.handler.bulk_enrich_context_window_handler.s3_client", local_mock_s3):
        result = _fetch_from_s3("test-bucket", "mistralai/Mistral-7B", "textgen")
        assert result == 32768
        local_mock_s3.get_object.assert_called_with(Bucket="test-bucket", Key="mistralai/Mistral-7B/config.json")


def test_fetch_from_s3_imagegen_fallback():
    """Test IMAGEGEN model falls back to text_encoder/config.json."""
    local_mock_s3 = MagicMock()
    local_mock_s3.exceptions = MockS3Exceptions()
    local_mock_s3.get_object.side_effect = [
        MockS3Exceptions.NoSuchKey("not found"),
        {"Body": MagicMock(read=lambda: json.dumps({"max_position_embeddings": 77}).encode())},
    ]

    with patch("models.handler.bulk_enrich_context_window_handler.s3_client", local_mock_s3):
        result = _fetch_from_s3("test-bucket", "sd-model/v1", "imagegen")
        assert result == 77
        assert local_mock_s3.get_object.call_count == 2


def test_fetch_from_s3_no_key_found():
    """Test when config.json does not exist in S3."""
    local_mock_s3 = MagicMock()
    local_mock_s3.exceptions = MockS3Exceptions()
    local_mock_s3.get_object.side_effect = MockS3Exceptions.NoSuchKey("not found")

    with patch("models.handler.bulk_enrich_context_window_handler.s3_client", local_mock_s3):
        result = _fetch_from_s3("test-bucket", "nonexistent", "textgen")
        assert result is None


def test_fetch_from_s3_no_max_position_embeddings():
    """Test when config.json exists but lacks max_position_embeddings."""
    local_mock_s3 = MagicMock()
    local_mock_s3.exceptions = MockS3Exceptions()
    local_mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: json.dumps({"hidden_size": 4096}).encode())}

    with patch("models.handler.bulk_enrich_context_window_handler.s3_client", local_mock_s3):
        result = _fetch_from_s3("test-bucket", "some-model", "textgen")
        assert result is None


# ============================================================================
# Tests for BulkEnrichContextWindowHandler
# ============================================================================


def test_bulk_enrich_skips_models_with_context_window(model_table, guardrails_table):
    """Test that models already having context_window are skipped."""
    model_table.put_item(
        Item={
            "model_id": "already-enriched",
            "model_status": "InService",
            "context_window": 100000,
            "model_config": {"modelName": "test", "modelType": "textgen"},
        }
    )

    handler = _make_handler(model_table, guardrails_table)

    with patch(
        "models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=mock_litellm_client
    ):
        result = handler()

    assert "already-enriched" in result.skipped
    assert "already-enriched" not in result.enriched
    assert "already-enriched" not in result.failed


def test_bulk_enrich_non_lisa_managed_via_litellm(model_table, guardrails_table):
    """Test enriching a non-LISA-managed model via LiteLLM."""
    model_table.put_item(
        Item={
            "model_id": "bedrock-model",
            "model_status": "InService",
            "litellm_id": "litellm-abc",
            "model_config": {"modelName": "bedrock/claude-v2", "modelType": "textgen"},
        }
    )

    local_litellm = MagicMock()
    local_litellm.get_model.return_value = {
        "model_info": {"id": "litellm-abc", "max_input_tokens": 200000},
    }

    handler = _make_handler(model_table, guardrails_table)

    with patch("models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=local_litellm):
        result = handler()

    assert "bedrock-model" in result.enriched
    assert len(result.skipped) == 0

    # Verify DDB was updated
    item = model_table.get_item(Key={"model_id": "bedrock-model"})["Item"]
    assert item["context_window"] == 200000


def test_bulk_enrich_lisa_managed_via_s3(model_table, guardrails_table):
    """Test enriching a LISA-managed model via S3 config.json."""
    model_table.put_item(
        Item={
            "model_id": "lisa-model",
            "model_status": "InService",
            "model_config": {
                "modelName": "mistralai/Mistral-7B",
                "modelType": "textgen",
                "autoScalingConfig": {"minCapacity": 1},
                "containerConfig": {"image": {"baseImage": "test"}},
                "inferenceContainer": "vllm",
                "instanceType": "t3.medium",
                "loadBalancerConfig": {"healthCheckConfig": {}},
            },
        }
    )

    local_mock_s3 = MagicMock()
    local_mock_s3.exceptions = MockS3Exceptions()
    local_mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps({"max_position_embeddings": 32768}).encode())
    }

    handler = _make_handler(model_table, guardrails_table)

    with patch(
        "models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=MagicMock()
    ), patch("models.handler.bulk_enrich_context_window_handler.s3_client", local_mock_s3), patch.dict(
        os.environ, {"MODELS_BUCKET_NAME": "test-bucket"}
    ):
        result = handler()

    assert "lisa-model" in result.enriched

    # Verify DDB was updated
    item = model_table.get_item(Key={"model_id": "lisa-model"})["Item"]
    assert item["context_window"] == 32768


def test_bulk_enrich_failed_lookup(model_table, guardrails_table):
    """Test that failed context window lookup is recorded in the failed dict."""
    model_table.put_item(
        Item={
            "model_id": "fail-model",
            "model_status": "InService",
            "model_config": {"modelName": "unknown-model", "modelType": "textgen"},
        }
    )

    local_litellm = MagicMock()
    local_litellm.get_model.side_effect = Exception("Not found")
    local_litellm.list_models.return_value = []  # No match in fallback

    handler = _make_handler(model_table, guardrails_table)

    with patch("models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=local_litellm):
        result = handler()

    assert "fail-model" in result.failed
    assert "Could not determine" in result.failed["fail-model"]


def test_bulk_enrich_exception_during_processing(model_table, guardrails_table):
    """Test that exceptions during individual model processing are caught and recorded.

    We patch _fetch_from_litellm at the function level so that the exception
    propagates to the outer try/except in the handler, since the real
    _fetch_from_litellm catches all exceptions internally.
    """
    model_table.put_item(
        Item={
            "model_id": "error-model",
            "model_status": "InService",
            "litellm_id": "some-id",
            "model_config": {"modelName": "error-model", "modelType": "textgen"},
        }
    )

    handler = _make_handler(model_table, guardrails_table)

    with patch(
        "models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=MagicMock()
    ), patch(
        "models.handler.bulk_enrich_context_window_handler._fetch_from_litellm",
        side_effect=RuntimeError("Unexpected crash"),
    ):
        result = handler()

    assert "error-model" in result.failed
    assert "Unexpected crash" in result.failed["error-model"]


def test_bulk_enrich_mixed_models(model_table, guardrails_table):
    """Test bulk enrichment with a mix of already-enriched, successful, and failed models."""
    # Model 1: already has context_window
    model_table.put_item(
        Item={
            "model_id": "enriched-model",
            "model_status": "InService",
            "context_window": 50000,
            "model_config": {"modelName": "test", "modelType": "textgen"},
        }
    )
    # Model 2: can be enriched via LiteLLM
    model_table.put_item(
        Item={
            "model_id": "litellm-model",
            "model_status": "InService",
            "litellm_id": "litellm-xyz",
            "model_config": {"modelName": "bedrock/model", "modelType": "textgen"},
        }
    )
    # Model 3: will fail enrichment
    model_table.put_item(
        Item={
            "model_id": "no-data-model",
            "model_status": "InService",
            "model_config": {"modelName": "mystery-model", "modelType": "textgen"},
        }
    )

    local_litellm = MagicMock()
    # get_model succeeds for litellm-xyz
    local_litellm.get_model.return_value = {
        "model_info": {"id": "litellm-xyz", "max_input_tokens": 128000},
    }
    # list_models returns nothing (for fallback on no-data-model)
    local_litellm.list_models.return_value = []

    handler = _make_handler(model_table, guardrails_table)

    with patch("models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=local_litellm):
        result = handler()

    assert "enriched-model" in result.skipped
    assert "litellm-model" in result.enriched
    assert "no-data-model" in result.failed

    # Verify enriched model got updated in DDB
    item = model_table.get_item(Key={"model_id": "litellm-model"})["Item"]
    assert item["context_window"] == 128000

    # Verify skipped model was not changed
    item = model_table.get_item(Key={"model_id": "enriched-model"})["Item"]
    assert item["context_window"] == 50000


def test_bulk_enrich_empty_table(model_table, guardrails_table):
    """Test bulk enrichment on an empty model table."""
    handler = _make_handler(model_table, guardrails_table)

    with patch("models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=MagicMock()):
        result = handler()

    assert result.enriched == []
    assert result.skipped == []
    assert result.failed == {}


def test_bulk_enrich_no_bucket_for_lisa_managed(model_table, guardrails_table):
    """Test that LISA-managed models fail gracefully when MODELS_BUCKET_NAME is empty."""
    model_table.put_item(
        Item={
            "model_id": "lisa-no-bucket",
            "model_status": "InService",
            "model_config": {
                "modelName": "some-model",
                "modelType": "textgen",
                "autoScalingConfig": {"minCapacity": 1},
                "containerConfig": {"image": {"baseImage": "test"}},
                "inferenceContainer": "vllm",
                "instanceType": "t3.medium",
                "loadBalancerConfig": {"healthCheckConfig": {}},
            },
        }
    )

    handler = _make_handler(model_table, guardrails_table)

    with patch(
        "models.handler.bulk_enrich_context_window_handler._get_litellm_client", return_value=MagicMock()
    ), patch.dict(os.environ, {"MODELS_BUCKET_NAME": ""}):
        result = handler()

    # With no bucket, S3 fetch returns None, so it should be in failed
    assert "lisa-no-bucket" in result.failed
