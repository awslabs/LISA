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

Tests document ingestion, listing, and deletion via the LISA SDK against a deployed environment. Requires: deployed LISA
with at least one repository and one embedding model.
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

# Default repository created by `npm run test:integ:setup`
DEFAULT_TEST_REPO_ID = os.environ.get("TEST_REPOSITORY_ID", "test-pgvector-rag")


class TestLisaRag:
    @pytest.fixture(autouse=True, scope="class")
    def setup_class(self, lisa_api: LisaApi, request: pytest.FixtureRequest) -> None:
        # Find the specific test repository
        repos = lisa_api.list_repositories()
        repo = next((r for r in repos if r.get("repositoryId") == DEFAULT_TEST_REPO_ID), None)
        if not repo:
            pytest.skip(f"Repository '{DEFAULT_TEST_REPO_ID}' not found — run `npm run test:integ:setup` first")

        request.cls.repo_id = repo.get("repositoryId", "")

        # Resolve embedding model: env var > repo's embeddingModelId > first embedding model from API
        embedding_model_id = os.environ.get("TEST_EMBEDDING_MODEL") or repo.get("embeddingModelId", "")
        if not embedding_model_id:
            models = lisa_api.list_embedding_models()
            if not models:
                pytest.skip("No embedding models deployed — run `npm run test:integ:setup` first")
            embedding_model_id = models[0].get("modelId", "")

        # For the default collection, collection_id == embeddingModelId
        request.cls.collection_id = embedding_model_id
        request.cls.embedding_model = embedding_model_id

    @pytest.fixture(autouse=True, scope="class")
    def cleanup_ingested_documents(self, lisa_api: LisaApi, setup_class: None) -> None:  # noqa: E501
        """Cleanup fixture that deletes any ingested documents after all tests complete."""
        yield  # Let tests run first

        doc_id = getattr(self.__class__, "_ingested_doc_id", None)
        if not doc_id:
            logger.info("CLEANUP: No ingested document to clean up")
            return

        repo_id = getattr(self, "repo_id", None)
        collection_id = getattr(self, "collection_id", None)
        if not repo_id or not collection_id:
            logger.warning("CLEANUP: Missing repo_id or collection_id, skipping cleanup")
            return

        try:
            logger.info(f"CLEANUP: Deleting ingested document {doc_id} from {repo_id}/{collection_id}")
            lisa_api.delete_document_by_ids(repo_id, collection_id, [doc_id])
            logger.info(f"CLEANUP: Successfully deleted document {doc_id}")
        except Exception:
            logger.exception(f"CLEANUP: Failed to delete document {doc_id} — ignoring")

    def _upload_and_ingest(self, lisa_api: LisaApi, content: str, prefix: str) -> str:
        """Upload and ingest a single temp file.

        Returns the s3Path from the ingestion job.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix=prefix, delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            filename = os.path.basename(temp_path)
            presigned_data = lisa_api._presigned_url(filename)
            s3_key = presigned_data.get("key")
            assert s3_key, "Presigned URL response missing 'key'"
            lisa_api._upload_document(presigned_data, temp_path)
            logger.info(f"Uploaded {filename} to S3 key: {s3_key}")

            jobs = lisa_api.ingest_document(
                self.repo_id,
                self.embedding_model,
                s3_key,
                collection_id=self.collection_id,
            )
            assert len(jobs) > 0, "ingest_document returned no jobs"
            s3_path = jobs[0].get("s3Path", "")
            assert s3_path, f"Ingestion job missing s3Path: {jobs[0]}"
            logger.info(f"Ingestion job: {jobs[0]}")
            return s3_path
        finally:
            os.unlink(temp_path)

    @staticmethod
    def _extract_doc_id(doc: dict) -> str | None:
        """Extract document ID from a document dict, handling both camelCase and snake_case."""
        return doc.get("document_id") or doc.get("documentId") or doc.get("id")

    def _wait_for_document(self, lisa_api: LisaApi, s3_path: str) -> str:
        """Poll until a document with matching source appears in list_documents.

        Returns its document_id.
        The ingest API returns s3Path (e.g. s3://bucket/key) which matches RagDocument.source exactly.
        """
        start = time.time()
        while time.time() - start < INGEST_TIMEOUT:
            documents = lisa_api.list_documents(self.repo_id, self.collection_id)
            for doc in documents:
                if doc.get("source") == s3_path:
                    doc_id = self._extract_doc_id(doc)
                    assert doc_id, f"Document matched source '{s3_path}' but has no extractable ID: {doc}"
                    logger.info(f"Document ingested as {doc_id} after {int(time.time() - start)}s")
                    return doc_id
            elapsed = int(time.time() - start)
            logger.info(f"Waiting for {s3_path}... ({elapsed}s elapsed, {len(documents)} docs found)")
            time.sleep(INGEST_POLL_INTERVAL)
        # Final attempt with full diagnostics
        documents = lisa_api.list_documents(self.repo_id, self.collection_id)
        sources = [(self._extract_doc_id(d), d.get("source")) for d in documents]
        pytest.fail(
            f"Document with source '{s3_path}' not found after {INGEST_TIMEOUT}s. "
            f"repo_id={self.repo_id}, collection_id={self.collection_id}, "
            f"found {len(documents)} docs: {sources}"
        )

    def test_01_insert_doc(self, lisa_api: LisaApi) -> None:
        """Insert a document into a collection and verify ingestion completes."""
        s3_path = self._upload_and_ingest(lisa_api, "LISA integration test document for RAG SDK.\n", "integ-test-")
        logger.info(f"Ingestion started for s3_path={s3_path}")

        # Poll until document appears; _wait_for_document returns the resolved document_id
        doc_id = self._wait_for_document(lisa_api, s3_path)
        self.__class__._ingested_doc_id = doc_id

    def test_02_list_docs(self, lisa_api: LisaApi) -> None:
        """List documents in a collection and verify the response structure."""
        documents = lisa_api.list_documents(self.repo_id, self.collection_id)
        logger.info(f"Found {len(documents)} documents in repo {self.repo_id} / collection {self.collection_id}")
        assert isinstance(documents, list)

    def test_03_delete_doc_by_ids(self, lisa_api: LisaApi) -> None:
        """Delete the ingested test document by ID and verify removal."""
        doc_id = getattr(self.__class__, "_ingested_doc_id", None)
        if not doc_id:
            pytest.skip("No ingested document ID from test_01 — skipping delete")

        response = lisa_api.delete_document_by_ids(self.repo_id, self.collection_id, [doc_id])
        logger.info(f"Delete by ID response: {response}")

        # Poll for eventual consistency — deletion may be async
        start = time.time()
        while time.time() - start < 60:
            remaining = lisa_api.list_documents(self.repo_id, self.collection_id)
            remaining_ids = {self._extract_doc_id(d) for d in remaining}
            if doc_id not in remaining_ids:
                logger.info(f"Document {doc_id} confirmed deleted after {int(time.time() - start)}s")
                self.__class__._ingested_doc_id = None
                return
            time.sleep(5)

        pytest.fail(f"Document {doc_id} still present after 60s")
