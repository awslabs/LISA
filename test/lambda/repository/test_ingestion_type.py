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

"""Unit tests for IngestionType enum and document provenance tracking."""

from models.domain_objects import IngestionType, NoneChunkingStrategy, RagDocument


class TestIngestionType:
    """Test IngestionType enum."""

    def test_ingestion_type_values(self):
        """Test that all IngestionType values exist."""
        assert IngestionType.MANUAL == "manual"
        assert IngestionType.AUTO == "auto"
        assert IngestionType.EXISTING == "existing"

    def test_ingestion_type_in_enum(self):
        """Test that all values are in the enum."""
        assert IngestionType.MANUAL in IngestionType
        assert IngestionType.AUTO in IngestionType
        assert IngestionType.EXISTING in IngestionType

    def test_ingestion_type_serialization(self):
        """Test that IngestionType serializes correctly."""
        doc = RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_name="test.pdf",
            source="s3://bucket/test.pdf",
            username="system",
            ingestion_type=IngestionType.EXISTING,
            chunk_strategy=NoneChunkingStrategy(),
        )

        serialized = doc.model_dump()
        assert serialized["ingestion_type"] == "existing"

    def test_ingestion_type_default(self):
        """Test that default ingestion_type is MANUAL."""
        doc = RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_name="test.pdf",
            source="s3://bucket/test.pdf",
            username="user1",
            chunk_strategy=NoneChunkingStrategy(),
        )

        assert doc.ingestion_type == IngestionType.MANUAL

    def test_ingestion_type_manual(self):
        """Test MANUAL ingestion type."""
        doc = RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_name="manual.pdf",
            source="s3://bucket/manual.pdf",
            username="user1",
            ingestion_type=IngestionType.MANUAL,
            chunk_strategy=NoneChunkingStrategy(),
        )

        assert doc.ingestion_type == IngestionType.MANUAL
        assert doc.ingestion_type == "manual"

    def test_ingestion_type_auto(self):
        """Test AUTO ingestion type."""
        doc = RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_name="auto.pdf",
            source="s3://bucket/auto.pdf",
            username="system",
            ingestion_type=IngestionType.AUTO,
            chunk_strategy=NoneChunkingStrategy(),
        )

        assert doc.ingestion_type == IngestionType.AUTO
        assert doc.ingestion_type == "auto"

    def test_ingestion_type_existing(self):
        """Test EXISTING ingestion type."""
        doc = RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_name="existing.pdf",
            source="s3://bucket/existing.pdf",
            username="system",
            ingestion_type=IngestionType.EXISTING,
            chunk_strategy=NoneChunkingStrategy(),
        )

        assert doc.ingestion_type == IngestionType.EXISTING
        assert doc.ingestion_type == "existing"

    def test_ingestion_type_comparison(self):
        """Test comparing ingestion types."""
        doc1 = RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_name="doc1.pdf",
            source="s3://bucket/doc1.pdf",
            username="user1",
            ingestion_type=IngestionType.MANUAL,
            chunk_strategy=NoneChunkingStrategy(),
        )

        doc2 = RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_name="doc2.pdf",
            source="s3://bucket/doc2.pdf",
            username="system",
            ingestion_type=IngestionType.EXISTING,
            chunk_strategy=NoneChunkingStrategy(),
        )

        assert doc1.ingestion_type != doc2.ingestion_type
        assert doc1.ingestion_type in [IngestionType.MANUAL, IngestionType.AUTO]
        assert doc2.ingestion_type == IngestionType.EXISTING

    def test_ingestion_type_filtering(self):
        """Test filtering documents by ingestion type."""
        docs = [
            RagDocument(
                repository_id="repo1",
                collection_id="col1",
                document_name=f"doc{i}.pdf",
                source=f"s3://bucket/doc{i}.pdf",
                username="user1" if i % 3 == 0 else "system",
                ingestion_type=(
                    IngestionType.MANUAL if i % 3 == 0 else IngestionType.AUTO if i % 3 == 1 else IngestionType.EXISTING
                ),
                chunk_strategy=NoneChunkingStrategy(),
            )
            for i in range(9)
        ]

        # Filter LISA-managed (MANUAL or AUTO)
        lisa_managed = [d for d in docs if d.ingestion_type in [IngestionType.MANUAL, IngestionType.AUTO]]
        assert len(lisa_managed) == 6

        # Filter user-managed (EXISTING)
        user_managed = [d for d in docs if d.ingestion_type == IngestionType.EXISTING]
        assert len(user_managed) == 3
