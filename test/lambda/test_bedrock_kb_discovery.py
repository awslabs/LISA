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

"""Tests for Bedrock Knowledge Base discovery utilities."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from utilities.bedrock_kb_discovery import (
    build_pipeline_configs_from_kb_config,
    discover_kb_data_sources,
    extract_s3_configuration,
    get_available_data_sources,
    list_knowledge_bases,
)
from utilities.validation import ValidationError


class TestListKnowledgeBases:
    """Test listing Knowledge Bases."""

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    def test_list_knowledge_bases_success(self, mock_bedrock_agent_client):
        """Test successful listing of Knowledge Bases."""
        # Arrange
        mock_bedrock_agent_client.list_knowledge_bases.return_value = {
            "knowledgeBaseSummaries": [
                {
                    "knowledgeBaseId": "KB123",
                    "name": "Test KB 1",
                    "description": "Test description 1",
                    "status": "ACTIVE",
                },
                {
                    "knowledgeBaseId": "KB456",
                    "name": "Test KB 2",
                    "description": "Test description 2",
                    "status": "ACTIVE",
                },
            ]
        }

        # Act
        result = list_knowledge_bases(bedrock_agent_client=mock_bedrock_agent_client)

        # Assert
        assert len(result) == 2
        assert result[0].knowledgeBaseId == "KB123"
        assert result[0].name == "Test KB 1"
        assert result[1].knowledgeBaseId == "KB456"
        mock_bedrock_agent_client.list_knowledge_bases.assert_called_once()

    def test_list_knowledge_bases_with_pagination(self, mock_bedrock_agent_client):
        """Test listing Knowledge Bases with pagination."""
        # Arrange
        mock_bedrock_agent_client.list_knowledge_bases.side_effect = [
            {
                "knowledgeBaseSummaries": [
                    {"knowledgeBaseId": "KB1", "name": "KB 1", "status": "ACTIVE"},
                ],
                "nextToken": "token123",
            },
            {
                "knowledgeBaseSummaries": [
                    {"knowledgeBaseId": "KB2", "name": "KB 2", "status": "ACTIVE"},
                ],
            },
        ]

        # Act
        result = list_knowledge_bases(bedrock_agent_client=mock_bedrock_agent_client)

        # Assert
        assert len(result) == 2
        assert result[0].knowledgeBaseId == "KB1"
        assert result[1].knowledgeBaseId == "KB2"
        assert mock_bedrock_agent_client.list_knowledge_bases.call_count == 2

    def test_list_knowledge_bases_access_denied(self, mock_bedrock_agent_client):
        """Test handling of access denied error."""
        # Arrange
        mock_bedrock_agent_client.list_knowledge_bases.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}, "ListKnowledgeBases"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Access denied to list Knowledge Bases"):
            list_knowledge_bases(bedrock_agent_client=mock_bedrock_agent_client)

    def test_list_knowledge_bases_throttling(self, mock_bedrock_agent_client):
        """Test handling of throttling error."""
        # Arrange
        mock_bedrock_agent_client.list_knowledge_bases.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}, "ListKnowledgeBases"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Rate limit exceeded"):
            list_knowledge_bases(bedrock_agent_client=mock_bedrock_agent_client)

    def test_list_knowledge_bases_generic_error(self, mock_bedrock_agent_client):
        """Test handling of generic error."""
        # Arrange
        mock_bedrock_agent_client.list_knowledge_bases.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Internal error"}}, "ListKnowledgeBases"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Failed to list Knowledge Bases"):
            list_knowledge_bases(bedrock_agent_client=mock_bedrock_agent_client)

    def test_list_knowledge_bases_unexpected_error(self, mock_bedrock_agent_client):
        """Test handling of unexpected error."""
        # Arrange
        mock_bedrock_agent_client.list_knowledge_bases.side_effect = Exception("Unexpected error")

        # Act & Assert
        with pytest.raises(ValidationError, match="Unexpected error listing Knowledge Bases"):
            list_knowledge_bases(bedrock_agent_client=mock_bedrock_agent_client)


class TestDiscoverKBDataSources:
    """Test discovering data sources in a Knowledge Base."""

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    def test_discover_data_sources_success(self, mock_bedrock_agent_client):
        """Test successful data source discovery."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.return_value = {
            "dataSourceSummaries": [
                {"dataSourceId": "DS123", "name": "Test DS 1"},
                {"dataSourceId": "DS456", "name": "Test DS 2"},
            ]
        }
        mock_bedrock_agent_client.get_data_source.side_effect = [
            {
                "dataSource": {
                    "dataSourceId": "DS123",
                    "name": "Test DS 1",
                    "status": "AVAILABLE",
                    "s3Bucket": "test-bucket-1",
                    "s3Prefix": "prefix1/",
                    "dataSourceConfiguration": {
                        "s3Configuration": {
                            "bucketArn": "arn:aws:s3:::test-bucket-1",
                            "inclusionPrefixes": ["prefix1/"],
                        }
                    },
                }
            },
            {
                "dataSource": {
                    "dataSourceId": "DS456",
                    "name": "Test DS 2",
                    "status": "AVAILABLE",
                    "s3Bucket": "test-bucket-2",
                    "s3Prefix": "",
                    "dataSourceConfiguration": {
                        "s3Configuration": {
                            "bucketArn": "arn:aws:s3:::test-bucket-2",
                            "inclusionPrefixes": [],
                        }
                    },
                }
            },
        ]

        # Act
        result = discover_kb_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)

        # Assert
        assert len(result) == 2
        assert result[0].dataSourceId == "DS123"
        assert result[1].dataSourceId == "DS456"
        mock_bedrock_agent_client.list_data_sources.assert_called_once()
        assert mock_bedrock_agent_client.get_data_source.call_count == 2

    def test_discover_data_sources_with_pagination(self, mock_bedrock_agent_client):
        """Test data source discovery with pagination."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.side_effect = [
            {
                "dataSourceSummaries": [{"dataSourceId": "DS1", "name": "DS 1"}],
                "nextToken": "token123",
            },
            {
                "dataSourceSummaries": [{"dataSourceId": "DS2", "name": "DS 2"}],
            },
        ]
        mock_bedrock_agent_client.get_data_source.side_effect = [
            {
                "dataSource": {
                    "dataSourceId": "DS1",
                    "name": "DS 1",
                    "status": "AVAILABLE",
                    "s3Bucket": "test-bucket",
                    "s3Prefix": "",
                    "dataSourceConfiguration": {
                        "s3Configuration": {
                            "bucketArn": "arn:aws:s3:::test-bucket",
                        }
                    },
                }
            },
            {
                "dataSource": {
                    "dataSourceId": "DS2",
                    "name": "DS 2",
                    "status": "AVAILABLE",
                    "s3Bucket": "test-bucket",
                    "s3Prefix": "",
                    "dataSourceConfiguration": {
                        "s3Configuration": {
                            "bucketArn": "arn:aws:s3:::test-bucket",
                        }
                    },
                }
            },
        ]

        # Act
        result = discover_kb_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)

        # Assert
        assert len(result) == 2
        assert mock_bedrock_agent_client.list_data_sources.call_count == 2

    def test_discover_data_sources_kb_not_found(self, mock_bedrock_agent_client):
        """Test handling of KB not found error."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "KB not found"}}, "ListDataSources"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Knowledge Base 'KB123' not found"):
            discover_kb_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)

    def test_discover_data_sources_access_denied(self, mock_bedrock_agent_client):
        """Test handling of access denied error."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}, "ListDataSources"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Access denied to Knowledge Base"):
            discover_kb_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)

    def test_discover_data_sources_throttling(self, mock_bedrock_agent_client):
        """Test handling of throttling error."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}, "ListDataSources"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Rate limit exceeded"):
            discover_kb_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)

    def test_discover_data_sources_generic_error(self, mock_bedrock_agent_client):
        """Test handling of generic error."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Internal error"}}, "ListDataSources"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Failed to discover data sources"):
            discover_kb_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)

    def test_discover_data_sources_unexpected_error(self, mock_bedrock_agent_client):
        """Test handling of unexpected error."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.side_effect = Exception("Unexpected error")

        # Act & Assert
        with pytest.raises(ValidationError, match="Unexpected error discovering data sources"):
            discover_kb_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)


class TestExtractS3Configuration:
    """Test extracting S3 configuration from data source."""

    def test_extract_s3_config_with_bucket_and_prefix(self):
        """Test extracting S3 config with bucket and prefix."""
        # Arrange
        data_source = {
            "dataSourceConfiguration": {
                "s3Configuration": {
                    "bucketArn": "arn:aws:s3:::my-test-bucket",
                    "inclusionPrefixes": ["documents/", "files/"],
                }
            }
        }

        # Act
        result = extract_s3_configuration(data_source)

        # Assert
        assert result["bucket"] == "my-test-bucket"
        assert result["prefix"] == "documents/"

    def test_extract_s3_config_without_prefix(self):
        """Test extracting S3 config without prefix."""
        # Arrange
        data_source = {
            "dataSourceConfiguration": {
                "s3Configuration": {
                    "bucketArn": "arn:aws:s3:::my-test-bucket",
                    "inclusionPrefixes": [],
                }
            }
        }

        # Act
        result = extract_s3_configuration(data_source)

        # Assert
        assert result["bucket"] == "my-test-bucket"
        assert result["prefix"] == ""

    def test_extract_s3_config_missing_config(self):
        """Test extracting S3 config when configuration is missing."""
        # Arrange
        data_source = {}

        # Act
        result = extract_s3_configuration(data_source)

        # Assert
        assert result["bucket"] == ""
        assert result["prefix"] == ""


class TestBuildPipelineConfigsFromKBConfig:
    """Test building pipeline configs from KB config."""

    def test_build_pipeline_configs_success(self):
        """Test successful pipeline config building."""
        # Arrange
        kb_config = {
            "knowledgeBaseId": "KB123",
            "dataSources": [
                {
                    "id": "DS123",
                    "name": "Data Source 1",
                    "s3Uri": "s3://bucket1/prefix1/",
                },
                {
                    "id": "DS456",
                    "name": "Data Source 2",
                    "s3Uri": "s3://bucket2/",
                },
            ],
        }

        # Act
        result = build_pipeline_configs_from_kb_config(kb_config)

        # Assert
        assert len(result) == 2
        assert result[0]["collectionId"] == "DS123"
        assert result[0]["collectionName"] == "Data Source 1"
        assert result[0]["s3Bucket"] == "bucket1"
        assert result[0]["s3Prefix"] == "prefix1/"
        assert result[1]["collectionId"] == "DS456"
        assert result[1]["s3Bucket"] == "bucket2"
        assert result[1]["s3Prefix"] == ""

    def test_build_pipeline_configs_duplicate_id(self):
        """Test handling of duplicate data source IDs."""
        # Arrange
        kb_config = {
            "dataSources": [
                {"id": "DS123", "name": "DS 1", "s3Uri": "s3://bucket1/"},
                {"id": "DS123", "name": "DS 2", "s3Uri": "s3://bucket2/"},
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Duplicate data source ID"):
            build_pipeline_configs_from_kb_config(kb_config)

    def test_build_pipeline_configs_duplicate_s3_uri(self):
        """Test handling of duplicate S3 URIs."""
        # Arrange
        kb_config = {
            "dataSources": [
                {"id": "DS123", "name": "DS 1", "s3Uri": "s3://bucket1/prefix/"},
                {"id": "DS456", "name": "DS 2", "s3Uri": "s3://bucket1/prefix/"},
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Duplicate S3 URI"):
            build_pipeline_configs_from_kb_config(kb_config)

    def test_build_pipeline_configs_missing_id(self):
        """Test handling of missing data source ID."""
        # Arrange
        kb_config = {
            "dataSources": [
                {"name": "DS 1", "s3Uri": "s3://bucket1/"},
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Data source ID is required"):
            build_pipeline_configs_from_kb_config(kb_config)

    def test_build_pipeline_configs_missing_name(self):
        """Test handling of missing data source name."""
        # Arrange
        kb_config = {
            "dataSources": [
                {"id": "DS123", "s3Uri": "s3://bucket1/"},
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Data source name is required"):
            build_pipeline_configs_from_kb_config(kb_config)

    def test_build_pipeline_configs_missing_s3_uri(self):
        """Test handling of missing S3 URI."""
        # Arrange
        kb_config = {
            "dataSources": [
                {"id": "DS123", "name": "DS 1"},
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="S3 URI is required"):
            build_pipeline_configs_from_kb_config(kb_config)

    def test_build_pipeline_configs_invalid_s3_uri(self):
        """Test handling of invalid S3 URI format."""
        # Arrange
        kb_config = {
            "dataSources": [
                {"id": "DS123", "name": "DS 1", "s3Uri": "http://bucket1/"},
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid S3 URI format"):
            build_pipeline_configs_from_kb_config(kb_config)

    def test_build_pipeline_configs_with_object_format(self):
        """Test building pipeline configs with object format (not dict)."""

        # Arrange
        class DataSource:
            def __init__(self, id, name, s3Uri):
                self.id = id
                self.name = name
                self.s3Uri = s3Uri

        class KBConfig:
            def __init__(self):
                self.dataSources = [
                    DataSource("DS123", "DS 1", "s3://bucket1/prefix/"),
                ]

        kb_config = KBConfig()

        # Act
        result = build_pipeline_configs_from_kb_config(kb_config)

        # Assert
        assert len(result) == 1
        assert result[0]["collectionId"] == "DS123"
        assert result[0]["s3Bucket"] == "bucket1"


class TestGetAvailableDataSources:
    """Test getting available data sources."""

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    def test_get_available_data_sources_success(self, mock_bedrock_agent_client):
        """Test successful retrieval of available data sources."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.return_value = {
            "dataSourceSummaries": [
                {"dataSourceId": "DS123", "name": "Test DS"},
            ]
        }
        mock_bedrock_agent_client.get_data_source.return_value = {
            "dataSource": {
                "dataSourceId": "DS123",
                "name": "Test DS",
                "status": "AVAILABLE",
                "s3Bucket": "test-bucket",
                "s3Prefix": "",
                "dataSourceConfiguration": {
                    "s3Configuration": {
                        "bucketArn": "arn:aws:s3:::test-bucket",
                    }
                },
            }
        }

        # Act
        result = get_available_data_sources(kb_id="KB123", bedrock_agent_client=mock_bedrock_agent_client)

        # Assert
        assert len(result) == 1
        assert result[0].dataSourceId == "DS123"

    def test_get_available_data_sources_with_repository_id(self, mock_bedrock_agent_client):
        """Test that repository_id parameter is accepted but unused."""
        # Arrange
        mock_bedrock_agent_client.list_data_sources.return_value = {"dataSourceSummaries": []}

        # Act
        result = get_available_data_sources(
            kb_id="KB123", repository_id="repo-123", bedrock_agent_client=mock_bedrock_agent_client
        )

        # Assert
        assert len(result) == 0
        mock_bedrock_agent_client.list_data_sources.assert_called_once()
