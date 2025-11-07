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

"""Unit tests for create_env_variables module."""

import os
from unittest.mock import Mock, patch

import pytest


class TestSetupEnvironment:
    """Test setup_environment function."""

    def test_setup_ssl_cert_file_when_not_set(self):
        """Test setting SSL_CERT_FILE when not already set."""
        # Import here to avoid module-level execution
        from utilities.create_env_variables import setup_environment
        
        with patch.dict(os.environ, {}, clear=True):
            # Remove SSL_CERT_FILE from environment
            if "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"]
            
            setup_environment()
            
            assert os.environ["SSL_CERT_FILE"] == "/etc/pki/tls/certs/ca-bundle.crt"

    def test_setup_ssl_cert_file_when_already_set(self):
        """Test that SSL_CERT_FILE is not overridden when already set."""
        from utilities.create_env_variables import setup_environment
        
        existing_cert_path = "/custom/cert/path.pem"
        with patch.dict(os.environ, {"SSL_CERT_FILE": existing_cert_path}):
            setup_environment()
            
            assert os.environ["SSL_CERT_FILE"] == existing_cert_path

    @patch('boto3.Session')
    def test_setup_aws_region_when_not_set(self, mock_session_class):
        """Test setting AWS_REGION when not already set."""
        from utilities.create_env_variables import setup_environment
        
        # Mock boto3 session
        mock_session = Mock()
        mock_session.region_name = "us-west-2"
        mock_session_class.return_value = mock_session
        
        with patch.dict(os.environ, {}, clear=True):
            # Remove AWS_REGION from environment
            if "AWS_REGION" in os.environ:
                del os.environ["AWS_REGION"]
            
            setup_environment()
            
            assert os.environ["AWS_REGION"] == "us-west-2"

    @patch('boto3.Session')
    def test_setup_aws_region_defaults_to_us_east_1(self, mock_session_class):
        """Test AWS_REGION defaults to us-east-1 when session has no region."""
        from utilities.create_env_variables import setup_environment
        
        # Mock boto3 session with no region
        mock_session = Mock()
        mock_session.region_name = None
        mock_session_class.return_value = mock_session
        
        with patch.dict(os.environ, {}, clear=True):
            # Remove AWS_REGION from environment
            if "AWS_REGION" in os.environ:
                del os.environ["AWS_REGION"]
            
            setup_environment()
            
            assert os.environ["AWS_REGION"] == "us-east-1"

    def test_setup_aws_region_when_already_set(self):
        """Test that AWS_REGION is not overridden when already set."""
        from utilities.create_env_variables import setup_environment
        
        existing_region = "eu-west-1"
        with patch.dict(os.environ, {"AWS_REGION": existing_region}):
            setup_environment()
            
            assert os.environ["AWS_REGION"] == existing_region

    @patch('boto3.Session')
    def test_setup_environment_both_variables(self, mock_session_class):
        """Test setting both environment variables when neither are set."""
        from utilities.create_env_variables import setup_environment
        
        # Mock boto3 session
        mock_session = Mock()
        mock_session.region_name = "ap-southeast-1"
        mock_session_class.return_value = mock_session
        
        with patch.dict(os.environ, {}, clear=True):
            # Remove both variables from environment
            for var in ["SSL_CERT_FILE", "AWS_REGION"]:
                if var in os.environ:
                    del os.environ[var]
            
            setup_environment()
            
            assert os.environ["SSL_CERT_FILE"] == "/etc/pki/tls/certs/ca-bundle.crt"
            assert os.environ["AWS_REGION"] == "ap-southeast-1"
