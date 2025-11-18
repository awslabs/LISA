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

"""Tests for repository service factory."""

import pytest
from repository.services.bedrock_kb_repository_service import BedrockKBRepositoryService
from repository.services.opensearch_repository_service import OpenSearchRepositoryService
from repository.services.pgvector_repository_service import PGVectorRepositoryService
from repository.services.repository_service_factory import RepositoryServiceFactory
from utilities.repository_types import RepositoryType


class TestRepositoryServiceFactory:
    """Test suite for RepositoryServiceFactory."""

    def test_create_opensearch_service(self):
        """Test creating OpenSearch service."""
        repository = {
            "repositoryId": "test-repo",
            "type": "opensearch",
            "endpoint": "test.opensearch.com"
        }
        
        service = RepositoryServiceFactory.create_service(repository)
        
        assert isinstance(service, OpenSearchRepositoryService)
        assert service.repository_id == "test-repo"
        assert service.supports_custom_collections() is True

    def test_create_pgvector_service(self):
        """Test creating PGVector service."""
        repository = {
            "repositoryId": "test-repo",
            "type": "pgvector",
            "dbHost": "localhost"
        }
        
        service = RepositoryServiceFactory.create_service(repository)
        
        assert isinstance(service, PGVectorRepositoryService)
        assert service.repository_id == "test-repo"
        assert service.supports_custom_collections() is True

    def test_create_bedrock_kb_service(self):
        """Test creating Bedrock KB service."""
        repository = {
            "repositoryId": "test-repo",
            "type": "bedrock_knowledge_base",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseId": "kb-123",
                "bedrockKnowledgeDatasourceId": "ds-456",
                "bedrockKnowledgeDatasourceS3Bucket": "test-bucket"
            }
        }
        
        service = RepositoryServiceFactory.create_service(repository)
        
        assert isinstance(service, BedrockKBRepositoryService)
        assert service.repository_id == "test-repo"
        assert service.supports_custom_collections() is False

    def test_create_service_unsupported_type(self):
        """Test creating service for unsupported type raises error."""
        repository = {
            "repositoryId": "test-repo",
            "type": "unsupported_type"
        }
        
        with pytest.raises(ValueError, match="Unsupported repository type"):
            RepositoryServiceFactory.create_service(repository)

    def test_get_supported_types(self):
        """Test getting list of supported repository types."""
        supported_types = RepositoryServiceFactory.get_supported_types()
        
        assert RepositoryType.OPENSEARCH in supported_types
        assert RepositoryType.PGVECTOR in supported_types
        assert RepositoryType.BEDROCK_KB in supported_types
        assert len(supported_types) == 3

    def test_register_custom_service(self):
        """Test registering a custom service class."""
        from repository.services.repository_service import RepositoryService
        
        class CustomRepositoryService(RepositoryService):
            def supports_custom_collections(self):
                return True
            
            def should_create_default_collection(self):
                return False
            
            # Implement other abstract methods...
        
        # Register custom service
        custom_type = RepositoryType("custom_type")
        RepositoryServiceFactory.register_service(custom_type, CustomRepositoryService)
        
        # Verify registration
        assert custom_type in RepositoryServiceFactory.get_supported_types()
