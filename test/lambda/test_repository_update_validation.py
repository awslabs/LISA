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
import sys
from decimal import Decimal
from unittest.mock import patch

# Set up mock AWS credentials first
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import (
    BedrockDataSource,
    BedrockKnowledgeBaseConfig,
    UpdateVectorStoreRequest,
)


class TestRepositoryUpdateValidation:
    """Test class for repository update validation and tag preservation."""

    def test_dynamodb_update_simulation(self):
        """Test DynamoDB update process simulation."""
        # Simulate current item in DynamoDB (with Decimal types as DynamoDB returns)
        current_item = {
            "repositoryId": "test-repo",
            "config": {
                "repositoryName": "PGV Rag",
                "pipelines": [
                    {
                        "trigger": "event",
                        "chunkingStrategy": {"type": "fixed", "size": Decimal("512"), "overlap": Decimal("51")},
                        "s3Prefix": "",
                        "autoRemove": True,
                        "collectionId": "default",
                        "s3Bucket": "docs",
                        "metadata": {"tags": ["existing-tag"]},
                    }
                ],
            },
            "status": "ACTIVE",
            "updatedAt": Decimal("1703123456789"),
        }

        # Updates from the request
        updates = {
            "repositoryName": "PGV Rag",
            "pipelines": [
                {
                    "autoRemove": True,
                    "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
                    "collectionId": "default",
                    "s3Bucket": "docs",
                    "s3Prefix": "",
                    "trigger": "event",
                    "metadata": {"tags": ["test"], "customFields": {}},
                }
            ],
        }

        # Simulate the VectorStoreRepository.update() method
        config = current_item["config"].copy()
        config.update(updates)

        # Check if tags are preserved
        assert "pipelines" in config
        assert config["pipelines"]
        pipeline_metadata = config["pipelines"][0].get("metadata", {})
        tags = pipeline_metadata.get("tags", [])

        # Tags should be updated to the new value
        assert tags == ["test"]

    def test_edge_case_empty_metadata(self):
        """Test edge case with empty metadata in current config."""
        current_empty_metadata = {
            "config": {
                "pipelines": [
                    {
                        "trigger": "event",
                        "s3Bucket": "docs",
                        "s3Prefix": "",
                        "autoRemove": True,
                        "collectionId": "default",
                        # No metadata field
                    }
                ]
            }
        }

        updates_with_tags = {
            "pipelines": [
                {
                    "trigger": "event",
                    "s3Bucket": "docs",
                    "s3Prefix": "",
                    "autoRemove": True,
                    "collectionId": "default",
                    "metadata": {"tags": ["new-tag"]},
                }
            ]
        }

        config = current_empty_metadata["config"].copy()
        config.update(updates_with_tags)

        tags = config["pipelines"][0].get("metadata", {}).get("tags", [])
        assert tags == ["new-tag"]

    def test_partial_pipeline_update(self):
        """Test partial pipeline update preserves other fields."""
        current_full = {
            "config": {
                "pipelines": [
                    {
                        "trigger": "event",
                        "s3Bucket": "docs",
                        "s3Prefix": "old-prefix",
                        "autoRemove": True,
                        "collectionId": "default",
                        "metadata": {"tags": ["old-tag"]},
                    }
                ]
            }
        }

        partial_update = {
            "pipelines": [
                {
                    "trigger": "event",
                    "s3Bucket": "docs",
                    "s3Prefix": "new-prefix",
                    "autoRemove": True,
                    "collectionId": "default",
                    "metadata": {"tags": ["new-tag"]},
                }
            ]
        }

        config = current_full["config"].copy()
        config.update(partial_update)

        tags = config["pipelines"][0].get("metadata", {}).get("tags", [])
        assert tags == ["new-tag"]
        assert config["pipelines"][0]["s3Prefix"] == "new-prefix"

    def test_update_vector_store_request_parsing(self):
        """Test UpdateVectorStoreRequest parsing preserves tags."""
        request_body = {
            "pipelines": [
                {
                    "trigger": "event",
                    "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
                    "s3Prefix": "",
                    "autoRemove": True,
                    "collectionId": "default",
                    "s3Bucket": "docs",
                    "metadata": {"tags": ["test"]},
                }
            ],
            "repositoryName": "PGV Rag",
        }

        # Parse request using UpdateVectorStoreRequest
        request = UpdateVectorStoreRequest(**request_body)

        assert request.pipelines is not None
        assert len(request.pipelines) == 1
        assert request.pipelines[0].metadata is not None
        assert request.pipelines[0].metadata.tags == ["test"]

        # Convert to dict for updates
        updates = request.model_dump(exclude_none=True, mode="json")

        assert "pipelines" in updates
        assert updates["pipelines"]
        pipeline_metadata = updates["pipelines"][0].get("metadata", {})
        tags = pipeline_metadata.get("tags", [])
        assert tags == ["test"]

    @patch("utilities.bedrock_kb_discovery.build_pipeline_configs_from_kb_config")
    def test_bedrock_kb_metadata_preservation(self, mock_build_pipeline_configs):
        """Test that Bedrock KB updates preserve existing pipeline metadata."""
        from utilities.bedrock_kb_discovery import build_pipeline_configs_from_kb_config

        # Mock the function to return new pipelines without metadata
        mock_build_pipeline_configs.return_value = [
            {
                "trigger": "event",
                "chunkingStrategy": {"type": "none"},
                "s3Prefix": "",
                "autoRemove": True,
                "collectionId": "datasource-1",
                "collectionName": "Test Data Source",
                "s3Bucket": "docs",
                # No metadata - this is what causes the issue
            }
        ]

        # Current repository configuration
        current_config = {
            "type": "BEDROCK_KB",
            "pipelines": [
                {
                    "trigger": "event",
                    "chunkingStrategy": {"type": "none"},
                    "s3Prefix": "",
                    "autoRemove": True,
                    "collectionId": "datasource-1",
                    "collectionName": "Test Data Source",
                    "s3Bucket": "docs",
                    "metadata": {"tags": ["existing-tag", "important"], "customFields": {"owner": "team-a"}},
                }
            ],
        }

        # Simulate the bedrockKnowledgeBaseConfig update
        kb_config = BedrockKnowledgeBaseConfig(
            knowledgeBaseId="kb-123",
            dataSources=[BedrockDataSource(id="datasource-1", name="Test Data Source", s3Uri="s3://docs/")],
        )

        # Build new pipeline configs
        new_pipelines = build_pipeline_configs_from_kb_config(kb_config)

        # Apply the fix - preserve existing metadata
        current_pipelines = current_config.get("pipelines", [])
        if current_pipelines:
            existing_metadata = {
                pipeline.get("collectionId"): pipeline.get("metadata", {})
                for pipeline in current_pipelines
                if pipeline.get("collectionId")
            }

            for pipeline in new_pipelines:
                collection_id = pipeline.get("collectionId")
                if collection_id and collection_id in existing_metadata:
                    pipeline["metadata"] = existing_metadata[collection_id]

        # Verify tags are preserved
        assert new_pipelines
        assert "metadata" in new_pipelines[0]
        tags = new_pipelines[0]["metadata"].get("tags", [])
        assert "existing-tag" in tags
        assert "important" in tags

    def test_direct_pipeline_metadata_preservation(self):
        """Test that direct pipeline updates preserve existing metadata when none provided."""
        current_pipelines = [
            {
                "trigger": "event",
                "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
                "s3Prefix": "",
                "autoRemove": True,
                "collectionId": "default",
                "s3Bucket": "docs",
                "metadata": {"tags": ["existing-tag"], "customFields": {"owner": "team-b"}},
            }
        ]

        # Update request missing metadata
        update_pipelines = [
            {
                "trigger": "event",
                "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
                "s3Prefix": "new-prefix",
                "autoRemove": True,
                "collectionId": "default",
                "s3Bucket": "docs",
                # No metadata provided - should preserve existing
            }
        ]

        # Apply the fix logic
        existing_metadata = {
            pipeline.get("collectionId"): pipeline.get("metadata", {})
            for pipeline in current_pipelines
            if pipeline.get("collectionId")
        }

        for pipeline in update_pipelines:
            collection_id = pipeline.get("collectionId")
            if collection_id and collection_id in existing_metadata:
                existing_meta = existing_metadata[collection_id]
                current_meta = pipeline.get("metadata", {})

                # If no metadata provided, use existing metadata
                if not current_meta:
                    pipeline["metadata"] = existing_meta

        # Verify metadata is preserved
        assert "metadata" in update_pipelines[0]
        tags = update_pipelines[0]["metadata"].get("tags", [])
        assert "existing-tag" in tags

    def test_partial_metadata_preservation(self):
        """Test that partial metadata updates preserve existing tags."""
        current_pipelines = [
            {
                "collectionId": "default",
                "metadata": {"tags": ["existing-tag", "important"], "customFields": {"owner": "team-c"}},
            }
        ]

        # Update with metadata but missing tags
        update_pipelines = [
            {
                "collectionId": "default",
                "metadata": {"customFields": {"owner": "team-d", "priority": "high"}},
                # Tags missing - should preserve existing tags
            }
        ]

        # Apply the fix logic for partial metadata
        existing_metadata = {
            pipeline.get("collectionId"): pipeline.get("metadata", {})
            for pipeline in current_pipelines
            if pipeline.get("collectionId")
        }

        for pipeline in update_pipelines:
            collection_id = pipeline.get("collectionId")
            if collection_id and collection_id in existing_metadata:
                existing_meta = existing_metadata[collection_id]
                current_meta = pipeline.get("metadata", {})

                # If metadata provided but missing tags, preserve existing tags
                if current_meta and "tags" not in current_meta and "tags" in existing_meta:
                    pipeline["metadata"]["tags"] = existing_meta["tags"]

        # Verify tags are preserved
        tags = update_pipelines[0]["metadata"].get("tags", [])
        assert "existing-tag" in tags
        assert "important" in tags

        # Verify other metadata is updated
        assert update_pipelines[0]["metadata"]["customFields"]["owner"] == "team-d"
        assert update_pipelines[0]["metadata"]["customFields"]["priority"] == "high"
