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

from lisa.domain.domain_objects import RetrieveResult
from lisa.rag.services.opensearch_repository_service import OpenSearchRepositoryService
from opensearchpy.exceptions import RequestError, TransportError


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
          - combination weights [0.3, 0.7] (lexical, vector) — defaults
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

    @pytest.mark.parametrize(
        "vector_weight,lexical_weight,expected_os_weights",
        [
            (0.8, 0.2, [0.2, 0.8]),  # OpenSearch order is [lexical, vector]
            (0.5, 0.5, [0.5, 0.5]),
            (1.0, 0.0, [0.0, 1.0]),
            (0.0, 1.0, [1.0, 0.0]),
        ],
        ids=["semantic-heavy", "balanced", "vector-only", "lexical-only"],
    )
    def test_hybrid_retrieve_applies_custom_weights(
        self, opensearch_service, vector_weight, lexical_weight, expected_os_weights
    ):
        """hybrid_retrieve passes caller-supplied weights to combination.parameters.weights.

        OpenSearch weights order is [lexical, vector] — opposite of the caller's perspective.
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
                query="test query",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
                vector_weight=vector_weight,
                lexical_weight=lexical_weight,
            )

        body = mock_vector_store.client.search.call_args.kwargs["body"]
        norm = body["search_pipeline"]["phase_results_processors"][0]["normalization-processor"]
        assert norm["combination"]["parameters"]["weights"] == expected_os_weights

    def test_hybrid_retrieve_uses_defaults_when_no_weights_specified(self, opensearch_service):
        """Without explicit weights, defaults to 0.7 vector / 0.3 lexical → [0.3, 0.7] in OpenSearch."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.return_value = {"hits": {"hits": []}}

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            opensearch_service.hybrid_retrieve(
                query="test query",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
            )

        body = mock_vector_store.client.search.call_args.kwargs["body"]
        norm = body["search_pipeline"]["phase_results_processors"][0]["normalization-processor"]
        assert norm["combination"]["parameters"]["weights"] == [0.3, 0.7]

    def test_hybrid_retrieve_returns_docs_and_hybrid_metadata(self, opensearch_service):
        """hybrid_retrieve returns RetrieveResult with actual_mode_used='hybrid'.

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
            result = opensearch_service.hybrid_retrieve(
                query="test",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
                include_score=True,
            )

        assert isinstance(result, RetrieveResult)
        assert len(result.documents) == 1
        assert result.documents[0]["page_content"] == "Hybrid result content"
        assert result.documents[0]["metadata"]["source"] == "s3://bucket/doc.pdf"
        assert result.documents[0]["metadata"]["similarity_score"] == 0.87
        assert result.actual_mode_used == "hybrid"
        assert result.hybrid_supported is True

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
            result = opensearch_service.hybrid_retrieve(
                query="test",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
            )

        assert len(result.documents) == 1
        assert "similarity_score" not in result.documents[0]["metadata"]

    def test_hybrid_retrieve_returns_empty_docs_with_hybrid_metadata(self, opensearch_service):
        """Empty hits still report actual_mode_used='hybrid' — metadata reports the mode that ran."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.return_value = {"hits": {"hits": []}}
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            result = opensearch_service.hybrid_retrieve(
                query="test",
                collection_id="test-collection",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
            )

        assert result.documents == []
        assert result.actual_mode_used == "hybrid"
        assert result.hybrid_supported is True

    def test_hybrid_retrieve_returns_empty_when_index_missing(self, opensearch_service):
        """hybrid_retrieve returns empty RetrieveResult when the target index does not exist."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = False
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            result = opensearch_service.hybrid_retrieve(
                query="test query",
                collection_id="nonexistent-index",
                top_k=5,
                model_name="amazon.titan-embed-text-v1",
            )

        assert result.documents == []
        assert result.actual_mode_used == "hybrid"
        assert result.hybrid_supported is True
        mock_vector_store.client.search.assert_not_called()

    def test_hybrid_retrieve_propagates_request_error(self, opensearch_service):
        """hybrid_retrieve bubbles up RequestError — no silent swallowing.

        OpenSearch errors (malformed query, auth, DSL validation) must propagate
        to the caller so they surface as actionable failures, not silent degradation.
        """
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.side_effect = RequestError(
            400,
            "parsing_exception",
            {"error": {"reason": "malformed query"}},
        )

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            with pytest.raises(RequestError) as exc_info:
                opensearch_service.hybrid_retrieve(
                    query="bad query",
                    collection_id="test-collection",
                    top_k=5,
                    model_name="amazon.titan-embed-text-v1",
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.error == "parsing_exception"

    def test_hybrid_retrieve_propagates_transport_error(self, opensearch_service):
        """hybrid_retrieve bubbles up TransportError — infrastructure failures must surface."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.search.side_effect = TransportError(
            503,
            "service_unavailable",
            {"error": {"reason": "cluster overloaded"}},
        )

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch(
            "lisa.rag.services.opensearch_repository_service.RagEmbeddings", return_value=mock_embeddings
        ), patch.object(opensearch_service, "_get_vector_store_client", return_value=mock_vector_store):
            with pytest.raises(TransportError) as exc_info:
                opensearch_service.hybrid_retrieve(
                    query="test",
                    collection_id="test-collection",
                    top_k=5,
                    model_name="amazon.titan-embed-text-v1",
                )

        assert exc_info.value.status_code == 503
