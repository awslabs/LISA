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

"""Tests for OpenSearch repository service."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")

from lisa.rag.services.opensearch_repository_service import OpenSearchRepositoryService


@pytest.fixture
def opensearch_repository():
    """Fixture for OpenSearch repository configuration."""
    return {
        "repositoryId": "test-opensearch-repo",
        "type": "opensearch",
        "name": "Test OpenSearch Repository",
        "endpoint": "test.opensearch.com",
        "embeddingModelId": "amazon.titan-embed-text-v1",
        "allowedGroups": ["admin"],
        "createdBy": "test-user",
    }


@pytest.fixture
def opensearch_service(opensearch_repository):
    """Fixture for OpenSearch service instance."""
    return OpenSearchRepositoryService(opensearch_repository)


class TestOpenSearchRepositoryService:
    """Test suite for OpenSearchRepositoryService."""

    def test_drop_collection_index_success(self, opensearch_service):
        """Test dropping OpenSearch index successfully."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.indices.delete.return_value = {"acknowledged": True}

        with patch("lisa.rag.services.opensearch_repository_service.RagEmbeddings"):
            with patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
                opensearch_service._drop_collection_index("test-collection")

                mock_vector_store.client.indices.exists.assert_called_once()
                mock_vector_store.client.indices.delete.assert_called_once()

    def test_drop_collection_index_not_exists(self, opensearch_service):
        """Test dropping OpenSearch index that doesn't exist."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = False

        with patch("lisa.rag.services.opensearch_repository_service.RagEmbeddings"):
            with patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
                opensearch_service._drop_collection_index("test-collection")

                mock_vector_store.client.indices.exists.assert_called_once()
                mock_vector_store.client.indices.delete.assert_not_called()

    def test_drop_collection_index_no_client_support(self, opensearch_service):
        """Test dropping index when vector store doesn't support index operations."""
        mock_vector_store = MagicMock(spec=[])  # No client attribute

        with patch("lisa.rag.services.opensearch_repository_service.RagEmbeddings"):
            with patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
                # Should not raise exception
                opensearch_service._drop_collection_index("test-collection")

    def test_drop_collection_index_exception(self, opensearch_service):
        """Test dropping index handles exceptions gracefully."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.side_effect = Exception("Connection error")

        with patch("lisa.rag.services.opensearch_repository_service.RagEmbeddings"):
            with patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
                # Should not raise exception
                opensearch_service._drop_collection_index("test-collection")

    def test_get_vector_store_client_parameter_not_found(self, opensearch_service):
        """Test _get_vector_store_client raises ValueError when SSM parameter not found."""
        from botocore.exceptions import ClientError

        mock_embeddings = MagicMock()

        # Create a proper ClientError for ParameterNotFound
        error_response = {"Error": {"Code": "ParameterNotFound", "Message": "Parameter not found"}}
        parameter_not_found = ClientError(error_response, "GetParameter")

        # Mock SSM client to raise ParameterNotFound
        with patch("lisa.rag.services.opensearch_repository_service.ssm_client") as mock_ssm:
            # Set up the exceptions attribute with ParameterNotFound
            mock_ssm.exceptions.ParameterNotFound = ClientError
            mock_ssm.get_parameter.side_effect = parameter_not_found

            with pytest.raises(ValueError) as exc_info:
                opensearch_service._get_vector_store_client("test-collection", mock_embeddings)

            assert "not registered" in str(exc_info.value)
            assert opensearch_service.repository_id in str(exc_info.value)

    def test_supports_hybrid_search(self, opensearch_service):
        """OpenSearch repositories advertise hybrid search capability."""
        assert opensearch_service.supports_hybrid_search() is True

    def test_hybrid_retrieve_sends_inline_pipeline(self, opensearch_service):
        """hybrid_retrieve sends an inline search_pipeline body with the hybrid query shape.

        Asserts the request body has:
          - query.hybrid.queries with both BM25 (match on `text`) and kNN (on `vector_field`)
          - search_pipeline.phase_results_processors with normalization-processor (min_max)
          - combination weights [0.3, 0.7] (lexical, vector) — hardcoded in slice 2.2.2
          - top_k preserved as `size`
        """
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.return_value = {"hits": {"hits": []}}

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            opensearch_service.hybrid_retrieve(
                query="exact phrase",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
            )

        mock_vector_store.client.search.assert_called_once()
        call_kwargs = mock_vector_store.client.search.call_args.kwargs
        assert call_kwargs["index"] == "test-collection"
        body = call_kwargs["body"]

        assert body["size"] == 5
        hybrid_queries = body["query"]["hybrid"]["queries"]
        assert {"match": {"text": {"query": "exact phrase"}}} in hybrid_queries
        knn_clause = next(q for q in hybrid_queries if "knn" in q)
        assert knn_clause["knn"]["vector_field"]["vector"] == [0.1, 0.2, 0.3]
        assert knn_clause["knn"]["vector_field"]["k"] == 5

        processors = body["search_pipeline"]["phase_results_processors"]
        norm = processors[0]["normalization-processor"]
        assert norm["normalization"]["technique"] == "min_max"
        assert norm["combination"]["technique"] == "arithmetic_mean"
        assert norm["combination"]["parameters"]["weights"] == [0.3, 0.7]

    def test_hybrid_retrieve_returns_docs_and_hybrid_metadata(self, opensearch_service):
        """hybrid_retrieve returns (docs, retrieval_metadata) with actual_mode_used='hybrid'.

        With include_score=True, copies hit['_score'] into metadata['similarity_score']
        (already 0-1 from min_max normalization — no further normalization needed).
        """
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.87,
                        "_source": {
                            "text": "Hybrid result content",
                            "metadata": {"source": "s3://bucket/doc.pdf"},
                        },
                    }
                ]
            }
        }
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            docs, retrieval_metadata = opensearch_service.hybrid_retrieve(
                query="test",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
                include_score=True,
            )

        assert len(docs) == 1
        assert docs[0]["page_content"] == "Hybrid result content"
        assert docs[0]["metadata"]["source"] == "s3://bucket/doc.pdf"
        assert docs[0]["metadata"]["similarity_score"] == 0.87
        assert retrieval_metadata["actual_mode_used"] == "hybrid"
        assert retrieval_metadata["hybrid_supported"] is True

    def test_hybrid_retrieve_omits_similarity_score_by_default(self, opensearch_service):
        """include_score=False (default) MUST NOT leak hit scores into doc metadata.

        Locks the default contract: callers that don't ask for scores don't get them.
        Without this assertion, a future refactor could populate similarity_score
        unconditionally and the happy-path test would still pass.
        """
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.42,
                        "_source": {
                            "text": "doc",
                            "metadata": {"source": "s3://b/d.pdf"},
                        },
                    }
                ]
            }
        }
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            docs, _ = opensearch_service.hybrid_retrieve(
                query="test",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
            )

        assert len(docs) == 1
        assert "similarity_score" not in docs[0]["metadata"]

    def test_hybrid_retrieve_returns_empty_docs_with_hybrid_metadata(self, opensearch_service):
        """Empty hits still report actual_mode_used='hybrid' — metadata reports the mode that ran.

        Mirrors BedrockKB's empty-fallback semantics: a caller distinguishing
        "ran hybrid, found nothing" from "fell back to vector" needs the metadata
        independent of whether docs is empty.
        """
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.return_value = {"hits": {"hits": []}}
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            docs, retrieval_metadata = opensearch_service.hybrid_retrieve(
                query="test",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
            )

        assert docs == []
        assert retrieval_metadata["actual_mode_used"] == "hybrid"
        assert retrieval_metadata["hybrid_supported"] is True
