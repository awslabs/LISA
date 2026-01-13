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

"""Unit tests for RagMixin."""

import tempfile
from typing import Dict

import pytest
import responses
from lisapy import LisaApi


class TestRagMixin:
    """Test suite for RAG-related operations."""

    @responses.activate
    def test_list_documents(self, lisa_api: LisaApi, api_url: str, mock_documents_response: Dict):
        """Test listing documents in a collection."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"

        responses.add(
            responses.GET, f"{api_url}/repository/{repo_id}/document", json=mock_documents_response, status=200
        )

        documents = lisa_api.list_documents(repo_id, collection_id)

        assert len(documents) == 2
        assert documents[0]["document_id"] == "doc-123"
        assert documents[1]["document_name"] == "another-doc.txt"
        # Verify query params
        assert responses.calls[0].request.params["collectionId"] == collection_id

    @responses.activate
    def test_get_document(self, lisa_api: LisaApi, api_url: str):
        """Test getting a single document by ID."""
        repo_id = "pgvector-rag"
        document_id = "doc-123"

        expected_response = {
            "document_id": document_id,
            "document_name": "test-document.pdf",
            "collection_id": "col-123",
            "source": "s3://bucket/test-document.pdf",
            "status": "READY",
        }

        responses.add(
            responses.GET, f"{api_url}/repository/{repo_id}/{document_id}", json=expected_response, status=200
        )

        document = lisa_api.get_document(repo_id, document_id)

        assert document["document_id"] == document_id
        assert document["document_name"] == "test-document.pdf"

    @responses.activate
    def test_delete_document_by_ids(self, lisa_api: LisaApi, api_url: str):
        """Test deleting documents by IDs."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"
        doc_ids = ["doc-123", "doc-456"]

        expected_response = {"jobs": [{"jobId": "job-1", "status": "PENDING", "documentIds": doc_ids}]}

        responses.add(responses.DELETE, f"{api_url}/repository/{repo_id}/document", json=expected_response, status=200)

        result = lisa_api.delete_document_by_ids(repo_id, collection_id, doc_ids)

        assert "jobs" in result
        assert result["jobs"][0]["documentIds"] == doc_ids
        # Verify request body and params
        assert responses.calls[0].request.params["collectionId"] == collection_id

    @responses.activate
    def test_delete_documents_by_name(self, lisa_api: LisaApi, api_url: str):
        """Test deleting documents by name."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"
        doc_name = "test-document.pdf"

        expected_response = {
            "jobs": [{"jobId": "job-2", "status": "PENDING", "documentName": doc_name}],
            "deletedCount": 1,
        }

        responses.add(responses.DELETE, f"{api_url}/repository/{repo_id}/document", json=expected_response, status=200)

        result = lisa_api.delete_documents_by_name(repo_id, collection_id, doc_name)

        assert "jobs" in result
        assert result["deletedCount"] == 1
        # Verify query params
        assert responses.calls[0].request.params["collectionId"] == collection_id
        assert responses.calls[0].request.params["documentName"] == doc_name

    @responses.activate
    def test_presigned_url(self, lisa_api: LisaApi, api_url: str):
        """Test getting a presigned URL for document upload."""
        file_name = "test-document.pdf"

        expected_response = {
            "response": {
                "url": "https://s3.amazonaws.com/bucket",
                "fields": {
                    "key": "uploads/test-document.pdf",
                    "AWSAccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                    "policy": "eyJleHBpcmF0aW9uIjogIjIwMjQtMDEtMjRUMTU6MDA6MDBaIn0=",
                    "signature": "signature-here",
                },
            }
        }

        responses.add(responses.POST, f"{api_url}/repository/presigned-url", json=expected_response, status=200)

        result = lisa_api._presigned_url(file_name)

        assert result["url"] == "https://s3.amazonaws.com/bucket"
        assert result["key"] == "uploads/test-document.pdf"
        assert "fields" in result

    @responses.activate
    def test_upload_document(self, lisa_api: LisaApi):
        """Test uploading a document using presigned POST."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_file = f.name

        presigned_data = {
            "url": "https://s3.amazonaws.com/bucket",
            "fields": {
                "key": "uploads/test.txt",
                "AWSAccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "policy": "policy-here",
                "signature": "signature-here",
            },
        }

        # Mock the S3 upload
        responses.add(responses.POST, "https://s3.amazonaws.com/bucket", status=204)

        result = lisa_api._upload_document(presigned_data, temp_file)

        assert result is True
        assert len(responses.calls) == 1

        # Cleanup
        import os

        os.unlink(temp_file)

    @responses.activate
    def test_ingest_document(self, lisa_api: LisaApi, api_url: str):
        """Test ingesting a document."""
        repo_id = "pgvector-rag"
        model_id = "amazon.titan-embed-text-v1"
        file_key = "uploads/test-document.pdf"
        collection_id = "col-123"

        expected_response = {
            "jobs": [
                {
                    "jobId": "job-123",
                    "documentId": "doc-new",
                    "status": "PENDING",
                    "s3Path": f"s3://bucket/{file_key}",
                }
            ]
        }

        responses.add(responses.POST, f"{api_url}/repository/{repo_id}/bulk", json=expected_response, status=200)

        jobs = lisa_api.ingest_document(repo_id=repo_id, model_id=model_id, file=file_key, collection_id=collection_id)

        assert len(jobs) == 1
        assert jobs[0]["jobId"] == "job-123"
        assert jobs[0]["status"] == "PENDING"

    @responses.activate
    def test_ingest_document_with_custom_chunking(self, lisa_api: LisaApi, api_url: str):
        """Test ingesting a document with custom chunking parameters."""
        repo_id = "pgvector-rag"
        model_id = "amazon.titan-embed-text-v1"
        file_key = "uploads/test-document.pdf"

        expected_response = {"jobs": [{"jobId": "job-124", "documentId": "doc-new-2", "status": "PENDING"}]}

        responses.add(responses.POST, f"{api_url}/repository/{repo_id}/bulk", json=expected_response, status=200)

        jobs = lisa_api.ingest_document(
            repo_id=repo_id, model_id=model_id, file=file_key, chuck_size=1024, chuck_overlap=102
        )

        assert len(jobs) == 1
        # Verify chunking params were sent
        assert responses.calls[0].request.params["chunkSize"] == "1024"
        assert responses.calls[0].request.params["chunkOverlap"] == "102"

    @responses.activate
    def test_similarity_search(self, lisa_api: LisaApi, api_url: str, caplog):
        """Test performing similarity search."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"
        query = "What is machine learning?"

        expected_response = {
            "docs": [
                {
                    "Document": {
                        "page_content": "Machine learning is a subset of AI...",
                        "metadata": {"source": "ml-guide.pdf", "page": 1},
                    },
                    "score": 0.95,
                },
                {
                    "Document": {
                        "page_content": "Deep learning uses neural networks...",
                        "metadata": {"source": "dl-guide.pdf", "page": 3},
                    },
                    "score": 0.87,
                },
            ]
        }

        responses.add(
            responses.GET, f"{api_url}/repository/{repo_id}/similaritySearch", json=expected_response, status=200
        )

        # Suppress logging errors from SDK code
        import logging

        logging.disable(logging.CRITICAL)

        docs = lisa_api.similarity_search(repo_id=repo_id, query=query, k=5, collection_id=collection_id)

        # Re-enable logging
        logging.disable(logging.NOTSET)

        assert len(docs) == 2
        assert docs[0]["score"] == 0.95
        assert "machine learning" in docs[0]["Document"]["page_content"].lower()
        # Verify query params
        assert responses.calls[0].request.params["query"] == query
        assert responses.calls[0].request.params["topK"] == "5"
        assert responses.calls[0].request.params["collectionId"] == collection_id

    @responses.activate
    def test_similarity_search_with_model_name(self, lisa_api: LisaApi, api_url: str):
        """Test similarity search with explicit model name."""
        repo_id = "pgvector-rag"
        query = "What is AI?"
        model_name = "amazon.titan-embed-text-v1"

        expected_response = {"docs": []}

        responses.add(
            responses.GET, f"{api_url}/repository/{repo_id}/similaritySearch", json=expected_response, status=200
        )

        docs = lisa_api.similarity_search(repo_id=repo_id, query=query, model_name=model_name)

        assert len(docs) == 0
        # Verify model_name was sent
        assert responses.calls[0].request.params["modelName"] == model_name

    @responses.activate
    def test_list_documents_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when listing documents fails."""
        repo_id = "pgvector-rag"
        collection_id = "col-123"

        responses.add(
            responses.GET, f"{api_url}/repository/{repo_id}/document", json={"error": "Not found"}, status=404
        )

        with pytest.raises(Exception):
            lisa_api.list_documents(repo_id, collection_id)

    @responses.activate
    def test_ingest_document_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when document ingestion fails."""
        repo_id = "pgvector-rag"
        model_id = "amazon.titan-embed-text-v1"
        file_key = "uploads/invalid.pdf"

        responses.add(
            responses.POST, f"{api_url}/repository/{repo_id}/bulk", json={"error": "Invalid file"}, status=400
        )

        with pytest.raises(Exception):
            lisa_api.ingest_document(repo_id=repo_id, model_id=model_id, file=file_key)
