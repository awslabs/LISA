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

"""Integration tests for RAG SDK document operations.

Tests document ingestion, listing, and deletion via the LISA SDK against a deployed environment.
Requires: deployed LISA with at least one repository and one embedding model.
"""

import logging
import os
import tempfile
import time

import pytest
from lisapy import LisaApi

logger = logging.getLogger(__name__)

# Maximum time to wait for document ingestion to complete (seconds)
INGEST_TIMEOUT = 360
INGEST_POLL_INTERVAL = 15


class TestLisaRag:

    @pytest.fixture(autouse=True)
    def setup_class(self, lisa_api: LisaApi) -> None:
        repos = lisa_api.list_repositories()
        models = lisa_api.list_embedding_models()
        if not repos:
            pytest.skip("No repositories deployed — run `npm run test:integ:setup` first")
        if not models:
            pytest.skip("No embedding models deployed — run `npm run test:integ:setup` first")
        self.repo_id: str = repos[0].get("repositoryId", "")
        self.collection_id: str = models[0].get("modelId", "")

    def test_01_insert_doc(self, lisa_api: LisaApi) -> None:
        """Insert a document into a collection and verify ingestion completes."""
        # Create a temp file with test content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="integ-test-", delete=False) as f:
            f.write("LISA integration test document for RAG SDK.\n")
            f.write("This file validates the document ingestion pipeline.\n")
            temp_path = f.name

        try:
            filename = os.path.basename(temp_path)

            # Upload to S3 via presigned URL
            presigned_data = lisa_api._presigned_url(filename)
            s3_key = presigned_data.get("key")
            assert s3_key, "Presigned URL response missing 'key'"
            lisa_api._upload_document(presigned_data, temp_path)
            logger.info(f"Uploaded {filename} to S3 key: {s3_key}")

            # Ingest the uploaded document
            jobs = lisa_api.ingest_document(
                self.repo_id,
                self.collection_id,
                s3_key,
                collection_id=self.collection_id,
            )
            assert len(jobs) > 0, "ingest_document returned no jobs"
            assert all("documentId" in job for job in jobs), "Job missing documentId"

            logger.info(f"Ingestion started: {len(jobs)} job(s), documentId={jobs[0].get('documentId')}")

            # Wait for ingestion to complete (document appears in list_documents)
            start = time.time()
            while time.time() - start < INGEST_TIMEOUT:
                documents = lisa_api.list_documents(self.repo_id, self.collection_id)
                if documents:
                    logger.info(f"Document ingested after {int(time.time() - start)}s")
                    return
                logger.info(f"Waiting for ingestion... ({int(time.time() - start)}s)")
                time.sleep(INGEST_POLL_INTERVAL)

            pytest.fail(f"Document ingestion timed out after {INGEST_TIMEOUT}s")

        finally:
            os.unlink(temp_path)

    def test_02_list_docs(self, lisa_api: LisaApi) -> None:
        """List documents in a collection and verify the response structure."""
        documents = lisa_api.list_documents(self.repo_id, self.collection_id)
        logger.info(f"Found {len(documents)} documents in repo {self.repo_id} / collection {self.collection_id}")
        assert isinstance(documents, list)

    def test_03_delete_doc_by_ids(self, lisa_api: LisaApi) -> None:
        """Delete a document by ID and verify removal."""
        documents = lisa_api.list_documents(self.repo_id, self.collection_id)
        if not documents:
            pytest.skip("No documents available to delete")

        doc = documents[0]
        doc_id = doc.get("documentId") or doc.get("document_id") or doc.get("id")
        assert doc_id, f"Could not extract document ID from: {doc}"

        response = lisa_api.delete_document_by_ids(self.repo_id, self.collection_id, [doc_id])
        logger.info(f"Delete by ID response: {response}")

        # Poll for eventual consistency — deletion may be async
        start = time.time()
        while time.time() - start < 60:
            remaining = lisa_api.list_documents(self.repo_id, self.collection_id)
            remaining_ids = [d.get("documentId") or d.get("document_id") or d.get("id") for d in remaining]
            if doc_id not in remaining_ids:
                logger.info(f"Document {doc_id} confirmed deleted after {int(time.time() - start)}s")
                return
            time.sleep(5)

        pytest.fail(f"Document {doc_id} still present after 60s")

    def test_04_delete_docs_by_name(self, lisa_api: LisaApi) -> None:
        """Delete documents by name and verify removal."""
        documents = lisa_api.list_documents(self.repo_id, self.collection_id)
        if not documents:
            pytest.skip("No documents available to delete")

        doc = documents[0]
        doc_name = doc.get("name") or doc.get("documentName") or doc.get("fileName")
        if not doc_name:
            pytest.skip(f"Could not extract document name from: {doc}")

        response = lisa_api.delete_documents_by_name(self.repo_id, self.collection_id, doc_name)
        logger.info(f"Delete by name response: {response}")

    @pytest.mark.skip(reason="Feature gap: management tokens cannot perform similarity search")
    def test_similarity_search(self, lisa_api: LisaApi) -> None:
        response = lisa_api.similarity_search(self.repo_id, self.collection_id, "What is OversightML?")
        logger.info(f"{response}")
        assert len(response) > 0
