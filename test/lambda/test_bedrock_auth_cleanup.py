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

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from models.bedrock_auth_cleanup import lambda_handler


class TestBedrockAuthCleanup:
    """Test cases for bedrock_auth_cleanup lambda function."""

    def test_lambda_handler_delete_request_type(self):
        """Test that DELETE request type returns SUCCESS without processing."""
        event = {'RequestType': 'Delete'}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result['Status'] == 'SUCCESS'
        assert result['PhysicalResourceId'] == 'bedrock-auth-cleanup'

    @patch('models.bedrock_auth_cleanup.boto3.client')
    @patch('models.bedrock_auth_cleanup.LiteLLMClient')
    @patch('models.bedrock_auth_cleanup.get_rest_api_container_endpoint')
    @patch('models.bedrock_auth_cleanup.get_cert_path')
    def test_lambda_handler_success_no_models(self, mock_get_cert, mock_get_endpoint, 
                                            mock_litellm_client_class, mock_boto3_client):
        """Test successful execution when no models are found."""
        # Setup mocks
        mock_secrets_manager = Mock()
        mock_iam_client = Mock()
        mock_boto3_client.side_effect = [mock_secrets_manager, mock_iam_client]
        
        mock_litellm_client = Mock()
        mock_litellm_client.list_models.return_value = []
        mock_litellm_client_class.return_value = mock_litellm_client
        
        mock_get_endpoint.return_value = "https://api.example.com"
        mock_get_cert.return_value = "/path/to/cert"
        
        mock_secrets_manager.get_secret_value.return_value = {
            "SecretString": "test-token"
        }
        
        # Setup environment
        with patch.dict('os.environ', {'AWS_REGION': 'us-east-1', 'MANAGEMENT_KEY_NAME': 'test-key'}):
            event = {'RequestType': 'Create'}
            context = Mock()
            
            result = lambda_handler(event, context)
            
            assert result['Status'] == 'SUCCESS'
            assert result['PhysicalResourceId'] == 'bedrock-auth-cleanup'

    @patch('models.bedrock_auth_cleanup.boto3.client')
    @patch('models.bedrock_auth_cleanup.LiteLLMClient')
    @patch('models.bedrock_auth_cleanup.get_rest_api_container_endpoint')
    @patch('models.bedrock_auth_cleanup.get_cert_path')
    def test_lambda_handler_success_with_bedrock_models(self, mock_get_cert, mock_get_endpoint,
                                                      mock_litellm_client_class, mock_boto3_client):
        """Test successful execution with Bedrock models that need cleanup."""
        # Setup mocks
        mock_secrets_manager = Mock()
        mock_iam_client = Mock()
        mock_boto3_client.side_effect = [mock_secrets_manager, mock_iam_client]
        
        mock_litellm_client = Mock()
        mock_litellm_client.list_models.return_value = [
            {
                'model_name': 'test-model-1',
                'model_info': {
                    'id': 'model-1',
                    'litellm_params': {
                        'model': 'bedrock/anthropic.claude-3-sonnet-20240229-v1:0',
                        'api_key': 'ignored'
                    }
                }
            },
            {
                'model_name': 'test-model-2', 
                'model_info': {
                    'id': 'model-2',
                    'litellm_params': {
                        'model': 'openai/gpt-4',
                        'api_key': 'sk-123'
                    }
                }
            }
        ]
        mock_litellm_client_class.return_value = mock_litellm_client
        
        mock_get_endpoint.return_value = "https://api.example.com"
        mock_get_cert.return_value = "/path/to/cert"
        
        mock_secrets_manager.get_secret_value.return_value = {
            "SecretString": "test-token"
        }
        
        # Setup environment
        with patch.dict('os.environ', {'AWS_REGION': 'us-east-1', 'MANAGEMENT_KEY_NAME': 'test-key'}):
            event = {'RequestType': 'Create'}
            context = Mock()
            
            result = lambda_handler(event, context)
            
            assert result['Status'] == 'SUCCESS'
            assert result['PhysicalResourceId'] == 'bedrock-auth-cleanup'
            assert result['Data']['ModelsUpdated'] == '1'
            
            # Verify delete and add_model were called for the Bedrock model
            mock_litellm_client.delete_model.assert_called_once_with(identifier='model-1')
            mock_litellm_client.add_model.assert_called_once()

    @patch('models.bedrock_auth_cleanup.boto3.client')
    def test_lambda_handler_exception(self, mock_boto3_client):
        """Test exception handling."""
        mock_boto3_client.side_effect = Exception("Test error")
        
        with patch.dict('os.environ', {'AWS_REGION': 'us-east-1'}):
            event = {'RequestType': 'Create'}
            context = Mock()
            
            result = lambda_handler(event, context)
            
            assert result['Status'] == 'FAILED'
            assert result['PhysicalResourceId'] == 'bedrock-auth-cleanup'
            assert 'Test error' in result['Reason']
