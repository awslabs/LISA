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

"""Unit tests for S3 event handler lambda function."""

import io
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

mock_env = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
    "DEPLOYMENT_PREFIX": "/test-deployment",
    "API_NAME": "serve",
    "MCP_WORKBENCH_ENDPOINT": "https://workbench.example.com",
    "WORKBENCH_RESCAN_DELAY_SECONDS": "0",
}


@pytest.fixture(autouse=True, scope="function")
def mock_common():
    """Ensure complete test isolation with fresh environment."""
    with patch.dict("os.environ", mock_env, clear=True):
        yield


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="s3_event_handler",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:s3_event_handler",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/s3_event_handler",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def sample_s3_event():
    """Create a sample S3 event from EventBridge."""
    return {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Object Created",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2024-03-27T12:00:00Z",
        "region": "us-east-1",
        "detail": {
            "version": "0",
            "bucket": {"name": "test-deployment-dev-mcpworkbench"},
            "object": {"key": "test-tool.py", "size": 1024, "etag": "test-etag"},
            "eventName": "s3:ObjectCreated:Put",
            "eventSource": "aws:s3",
        },
    }


def test_handler_success(lambda_context, sample_s3_event):
    """Test successful S3 event handling (HTTP rescan path)."""
    from mcp_workbench.s3_event_handler import handler

    rescan = {"rescan_status_code": 200, "rescan_body": '{"ok": true}'}

    with patch("mcp_workbench.s3_event_handler.trigger_workbench_rescan", return_value=rescan):
        response = handler(sample_s3_event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "MCP Workbench tools refresh triggered"
    assert body["bucket"] == "test-deployment-dev-mcpworkbench"
    assert body["event"] == "s3:ObjectCreated:Put"
    assert body["rescan"] == rescan


def test_handler_missing_bucket_name(lambda_context):
    """Test handling of event with missing bucket name."""
    event = {"detail": {"eventName": "s3:ObjectCreated:Put"}}

    from mcp_workbench.s3_event_handler import handler

    response = handler(event, lambda_context)

    assert response["statusCode"] == 400
    assert "Missing bucket name" in response["body"]


def test_handler_rescan_error_returns_502(lambda_context, sample_s3_event):
    """Test handling when workbench rescan reports an HTTP or transport error."""
    from mcp_workbench.s3_event_handler import handler

    rescan = {"rescan_error": True, "rescan_status_code": 503, "rescan_body": "unavailable"}

    with patch("mcp_workbench.s3_event_handler.trigger_workbench_rescan", return_value=rescan):
        response = handler(sample_s3_event, lambda_context)

    assert response["statusCode"] == 502
    body = json.loads(response["body"])
    assert body["rescan"] == rescan


def test_handler_unexpected_exception(lambda_context, sample_s3_event):
    """Test handling when trigger_workbench_rescan raises."""
    from mcp_workbench.s3_event_handler import handler

    with patch(
        "mcp_workbench.s3_event_handler.trigger_workbench_rescan",
        side_effect=RuntimeError("boom"),
    ):
        response = handler(sample_s3_event, lambda_context)

    assert response["statusCode"] == 500
    assert "boom" in response["body"]


def test_trigger_workbench_rescan_skipped_no_endpoint():
    """When MCP_WORKBENCH_ENDPOINT is unset, rescan is skipped."""
    from mcp_workbench.s3_event_handler import trigger_workbench_rescan

    with patch.dict("os.environ", {**mock_env, "MCP_WORKBENCH_ENDPOINT": ""}, clear=True):
        out = trigger_workbench_rescan()

    assert out == {"skipped": True, "reason": "MCP_WORKBENCH_ENDPOINT unset"}


def test_trigger_workbench_rescan_skipped_invalid_url():
    """Invalid endpoint URL returns skipped."""
    from mcp_workbench.s3_event_handler import trigger_workbench_rescan

    with patch.dict("os.environ", {**mock_env, "MCP_WORKBENCH_ENDPOINT": "not-a-url"}, clear=True):
        out = trigger_workbench_rescan()

    assert out["skipped"] is True
    assert "http" in out["reason"].lower()


def test_trigger_workbench_rescan_success():
    """Successful GET to rescan URL."""
    from mcp_workbench.s3_event_handler import trigger_workbench_rescan

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"refreshed": true}'

    with patch("mcp_workbench.s3_event_handler.time.sleep"):
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            out = trigger_workbench_rescan()

    assert out["rescan_status_code"] == 200
    assert '{"refreshed": true}' in out["rescan_body"]
    open_kw = mock_open.call_args[1]
    assert open_kw.get("context") is not None
    assert open_kw["context"].check_hostname is False


def test_trigger_workbench_rescan_http_error():
    """HTTPError from workbench is captured in result dict."""
    import urllib.error

    from mcp_workbench.s3_event_handler import trigger_workbench_rescan

    err = urllib.error.HTTPError(
        url="https://workbench.example.com/v2/mcp/rescan",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b"denied"),
    )

    with patch("mcp_workbench.s3_event_handler.time.sleep"):
        with patch("urllib.request.urlopen", side_effect=err):
            out = trigger_workbench_rescan()

    assert out["rescan_error"] is True
    assert out["rescan_status_code"] == 401


def test_management_bearer_token_none_without_secret():
    """No MANAGEMENT_KEY_NAME means no bearer token."""
    from mcp_workbench.s3_event_handler import _management_bearer_token

    with patch.dict("os.environ", {k: v for k, v in mock_env.items() if k != "MANAGEMENT_KEY_NAME"}, clear=True):
        assert _management_bearer_token() is None


def test_management_bearer_token_from_secrets():
    """MANAGEMENT_KEY_NAME loads secret string."""
    from mcp_workbench.s3_event_handler import _management_bearer_token

    env = {**mock_env, "MANAGEMENT_KEY_NAME": "lisa/mgmt-key"}
    with patch.dict("os.environ", env, clear=True):
        with patch("mcp_workbench.s3_event_handler.secrets_client") as mock_sm:
            mock_sm.get_secret_value.return_value = {"SecretString": "secret-token"}
            token = _management_bearer_token()

    assert token == "secret-token"
    mock_sm.get_secret_value.assert_called_once()


def test_management_bearer_token_secrets_error_reraises():
    """ClientError from Secrets Manager is re-raised after logging."""
    from mcp_workbench.s3_event_handler import _management_bearer_token

    env = {**mock_env, "MANAGEMENT_KEY_NAME": "lisa/mgmt-key"}
    with patch.dict("os.environ", env, clear=True):
        with patch("mcp_workbench.s3_event_handler.secrets_client") as mock_sm:
            mock_sm.get_secret_value.side_effect = ClientError(
                error_response={"Error": {"Code": "ResourceNotFoundException"}},
                operation_name="GetSecretValue",
            )
            with pytest.raises(ClientError):
                _management_bearer_token()


def test_validate_s3_event_valid():
    """Test validation of valid S3 event."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    valid_event = {"source": "aws.s3", "detail-type": "Object Created", "detail": {"bucket": {"name": "test-bucket"}}}

    assert validate_s3_event(valid_event) is True


def test_validate_s3_event_invalid_source():
    """Test validation of S3 event with invalid source."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    invalid_event = {
        "source": "aws.ec2",
        "detail-type": "Object Created",
        "detail": {"bucket": {"name": "test-bucket"}},
    }

    assert validate_s3_event(invalid_event) is False


def test_validate_s3_event_invalid_detail_type():
    """Test validation of S3 event with invalid detail type."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    invalid_event = {
        "source": "aws.s3",
        "detail-type": "Instance State Change",
        "detail": {"bucket": {"name": "test-bucket"}},
    }

    assert validate_s3_event(invalid_event) is False


def test_validate_s3_event_missing_bucket():
    """Test validation of S3 event with missing bucket name."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    invalid_event = {"source": "aws.s3", "detail-type": "Object Created", "detail": {}}

    assert validate_s3_event(invalid_event) is False


def test_validate_s3_event_debug_source():
    """Test validation of S3 event with debug source."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    debug_event = {"source": "debug", "detail-type": "Object Created", "detail": {"bucket": {"name": "test-bucket"}}}

    assert validate_s3_event(debug_event) is True
