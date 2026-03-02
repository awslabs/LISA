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

"""Unit tests for LISA SDK utils."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lisa-sdk"))

from lisapy.utils import get_cert_path


@patch.dict(os.environ, {}, clear=True)
def test_get_cert_path_no_cert_arn():
    """Test get_cert_path with no SSL cert ARN."""
    mock_iam_client = MagicMock()

    result = get_cert_path(mock_iam_client)

    assert result is True
    mock_iam_client.get_server_certificate.assert_not_called()


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": ""})
def test_get_cert_path_empty_cert_arn():
    """Test get_cert_path with empty SSL cert ARN."""
    mock_iam_client = MagicMock()

    result = get_cert_path(mock_iam_client)

    assert result is True


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:acm:us-east-1:123456789012:certificate/abc123"})
def test_get_cert_path_acm_cert():
    """Test get_cert_path with ACM certificate."""
    mock_iam_client = MagicMock()

    result = get_cert_path(mock_iam_client)

    assert result is True
    mock_iam_client.get_server_certificate.assert_not_called()


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/my-cert"})
def test_get_cert_path_iam_cert():
    """Test get_cert_path with IAM certificate."""
    mock_iam_client = MagicMock()
    mock_iam_client.get_server_certificate.return_value = {
        "ServerCertificate": {
            "CertificateBody": "-----BEGIN CERTIFICATE-----\ntest-cert-body\n-----END CERTIFICATE-----"
        }
    }

    result = get_cert_path(mock_iam_client)

    assert isinstance(result, str)
    assert os.path.exists(result)

    # Verify cert was written to file
    with open(result) as f:
        content = f.read()
        assert "BEGIN CERTIFICATE" in content

    # Cleanup
    os.unlink(result)

    mock_iam_client.get_server_certificate.assert_called_once_with(ServerCertificateName="my-cert")


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/test-cert"})
def test_get_cert_path_cert_content():
    """Test get_cert_path writes correct certificate content."""
    mock_iam_client = MagicMock()
    cert_body = "-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----"
    mock_iam_client.get_server_certificate.return_value = {"ServerCertificate": {"CertificateBody": cert_body}}

    result = get_cert_path(mock_iam_client)

    # Verify file content
    with open(result) as f:
        content = f.read()
        assert content == cert_body

    # Cleanup
    os.unlink(result)


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/cert-name"})
def test_get_cert_path_extracts_cert_name():
    """Test get_cert_path correctly extracts certificate name from ARN."""
    mock_iam_client = MagicMock()
    mock_iam_client.get_server_certificate.return_value = {"ServerCertificate": {"CertificateBody": "test-cert"}}

    result = get_cert_path(mock_iam_client)

    # Verify correct cert name was used
    mock_iam_client.get_server_certificate.assert_called_once_with(ServerCertificateName="cert-name")

    # Cleanup
    if isinstance(result, str) and os.path.exists(result):
        os.unlink(result)


@patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/my-cert"})
def test_get_cert_path_iam_error():
    """Test get_cert_path handles IAM errors."""
    mock_iam_client = MagicMock()
    mock_iam_client.get_server_certificate.side_effect = Exception("IAM error")

    with pytest.raises(Exception) as exc_info:
        get_cert_path(mock_iam_client)

    assert "IAM error" in str(exc_info.value)
