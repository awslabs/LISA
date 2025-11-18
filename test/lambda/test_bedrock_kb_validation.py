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

"""Tests for Bedrock Knowledge Base validation utilities."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from utilities.bedrock_kb_validation import (
    validate_bedrock_kb_exists,
    validate_bedrock_kb_repository,
    validate_data_source_exists,
)
from utilities.validation import ValidationError


class TestValidateBedrockKBExists:
    """Test Knowledge Base existence validation."""

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    def test_validate_kb_exists_success(self, mock_bedrock_agent_client):
        """Test successful KB validation."""
        # Arrange
        mock_bedrock_agent_client.get_knowledge_base.return_value = {
            "knowledgeBase": {
                "knowledgeBaseId": "KB123456",
                "name": "Test Knowledge Base",
                "status": "ACTIVE",
            }
        }

        # Act
        result = validate_bedrock_kb_exists(kb_id="KB123456", bedrock_agent_client=mock_bedrock_agent_client)

        # Assert
        assert result["knowledgeBaseId"] == "KB123456"
        assert result["name"] == "Test Knowledge Base"
        mock_bedrock_agent_client.get_knowledge_base.assert_called_once_with(knowledgeBaseId="KB123456")

    def test_validate_kb_not_found(self, mock_bedrock_agent_client):
        """Test KB not found error."""
        # Arrange
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "KB not found"}}
        mock_bedrock_agent_client.get_knowledge_base.side_effect = ClientError(error_response, "GetKnowledgeBase")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_bedrock_kb_exists(kb_id="KB123456", bedrock_agent_client=mock_bedrock_agent_client)

        assert "not found" in str(exc_info.value)
        assert "KB123456" in str(exc_info.value)

    def test_validate_kb_access_denied(self, mock_bedrock_agent_client):
        """Test access denied error."""
        # Arrange
        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}
        mock_bedrock_agent_client.get_knowledge_base.side_effect = ClientError(error_response, "GetKnowledgeBase")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_bedrock_kb_exists(kb_id="KB123456", bedrock_agent_client=mock_bedrock_agent_client)

        assert "Access denied" in str(exc_info.value)
        assert "IAM permissions" in str(exc_info.value)

    def test_validate_kb_other_client_error(self, mock_bedrock_agent_client):
        """Test other client errors."""
        # Arrange
        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_bedrock_agent_client.get_knowledge_base.side_effect = ClientError(error_response, "GetKnowledgeBase")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_bedrock_kb_exists(kb_id="KB123456", bedrock_agent_client=mock_bedrock_agent_client)

        assert "Failed to validate" in str(exc_info.value)

    def test_validate_kb_unexpected_error(self, mock_bedrock_agent_client):
        """Test unexpected errors."""
        # Arrange
        mock_bedrock_agent_client.get_knowledge_base.side_effect = Exception("Unexpected error")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_bedrock_kb_exists(kb_id="KB123456", bedrock_agent_client=mock_bedrock_agent_client)

        assert "Unexpected error" in str(exc_info.value)


class TestValidateDataSourceExists:
    """Test Data Source existence validation."""

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    def test_validate_data_source_success(self, mock_bedrock_agent_client):
        """Test successful data source validation."""
        # Arrange
        mock_bedrock_agent_client.get_data_source.return_value = {
            "dataSource": {
                "dataSourceId": "DS123456",
                "name": "Test Data Source",
                "status": "AVAILABLE",
            }
        }

        # Act
        result = validate_data_source_exists(
            kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
        )

        # Assert
        assert result["dataSourceId"] == "DS123456"
        assert result["name"] == "Test Data Source"
        mock_bedrock_agent_client.get_data_source.assert_called_once_with(
            knowledgeBaseId="KB123456", dataSourceId="DS123456"
        )

    def test_validate_data_source_not_found(self, mock_bedrock_agent_client):
        """Test data source not found error."""
        # Arrange
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Data source not found"}}
        mock_bedrock_agent_client.get_data_source.side_effect = ClientError(error_response, "GetDataSource")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_data_source_exists(
                kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
            )

        assert "not found" in str(exc_info.value)
        assert "DS123456" in str(exc_info.value)
        assert "KB123456" in str(exc_info.value)

    def test_validate_data_source_access_denied(self, mock_bedrock_agent_client):
        """Test access denied error."""
        # Arrange
        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}
        mock_bedrock_agent_client.get_data_source.side_effect = ClientError(error_response, "GetDataSource")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_data_source_exists(
                kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
            )

        assert "Access denied" in str(exc_info.value)
        assert "IAM permissions" in str(exc_info.value)

    def test_validate_data_source_other_error(self, mock_bedrock_agent_client):
        """Test other client errors."""
        # Arrange
        error_response = {"Error": {"Code": "ValidationException", "Message": "Invalid request"}}
        mock_bedrock_agent_client.get_data_source.side_effect = ClientError(error_response, "GetDataSource")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_data_source_exists(
                kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
            )

        assert "Failed to validate" in str(exc_info.value)

    def test_validate_data_source_unexpected_error(self, mock_bedrock_agent_client):
        """Test unexpected errors."""
        # Arrange
        mock_bedrock_agent_client.get_data_source.side_effect = Exception("Network error")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_data_source_exists(
                kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
            )

        assert "Unexpected error" in str(exc_info.value)


class TestValidateBedrockKBRepository:
    """Test complete repository validation."""

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    def test_validate_repository_success(self, mock_bedrock_agent_client):
        """Test successful repository validation."""
        # Arrange
        mock_bedrock_agent_client.get_knowledge_base.return_value = {
            "knowledgeBase": {
                "knowledgeBaseId": "KB123456",
                "name": "Test KB",
            }
        }
        mock_bedrock_agent_client.get_data_source.return_value = {
            "dataSource": {
                "dataSourceId": "DS123456",
                "name": "Test DS",
            }
        }

        # Act
        kb_config, ds_config = validate_bedrock_kb_repository(
            kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
        )

        # Assert
        assert kb_config["knowledgeBaseId"] == "KB123456"
        assert ds_config["dataSourceId"] == "DS123456"

        # Verify both API calls were made
        mock_bedrock_agent_client.get_knowledge_base.assert_called_once_with(knowledgeBaseId="KB123456")
        mock_bedrock_agent_client.get_data_source.assert_called_once_with(
            knowledgeBaseId="KB123456", dataSourceId="DS123456"
        )

    def test_validate_repository_kb_not_found(self, mock_bedrock_agent_client):
        """Test repository validation fails when KB not found."""
        # Arrange
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "KB not found"}}
        mock_bedrock_agent_client.get_knowledge_base.side_effect = ClientError(error_response, "GetKnowledgeBase")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_bedrock_kb_repository(
                kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
            )

        assert "not found" in str(exc_info.value)
        # Data source should not be checked if KB validation fails
        mock_bedrock_agent_client.get_data_source.assert_not_called()

    def test_validate_repository_data_source_not_found(self, mock_bedrock_agent_client):
        """Test repository validation fails when data source not found."""
        # Arrange
        mock_bedrock_agent_client.get_knowledge_base.return_value = {
            "knowledgeBase": {"knowledgeBaseId": "KB123456", "name": "Test KB"}
        }
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Data source not found"}}
        mock_bedrock_agent_client.get_data_source.side_effect = ClientError(error_response, "GetDataSource")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_bedrock_kb_repository(
                kb_id="KB123456", data_source_id="DS123456", bedrock_agent_client=mock_bedrock_agent_client
            )

        assert "not found" in str(exc_info.value)
        # KB should be validated first
        mock_bedrock_agent_client.get_knowledge_base.assert_called_once()
