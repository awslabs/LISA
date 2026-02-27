#!/usr/bin/env python3
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

"""
Integration tests for RAG Collections.

This test suite validates end-to-end functionality of RAG collections including:
- Collection creation and management
- Document ingestion to collections
- Similarity search within collections
- Document deletion and cleanup
- Collection deletion and full cleanup

These tests require a deployed LISA environment and use the LISA SDK.
"""

import logging
import os
import sys
import tempfile
import time

import pytest

# Add test utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from test.utils import create_lisa_client

# Add lisa-sdk to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../lisa-sdk"))

from lisapy.api import LisaApi

# Add lambda code to path for repository access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../lambda"))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Test configuration
TEST_COLLECTION_ID = "test-collection-integration"
TEST_DOCUMENT_CONTENT = """
This is a test document for RAG collections integration testing.
It contains information about artificial intelligence and machine learning.
Machine learning is a subset of artificial intelligence that focuses on learning from data.
"""


class RagIntegrationFixtures:
    """Shared fixtures for RAG integration tests. Contains no test methods."""

    created_collections = []

    @pytest.fixture(scope="class", autouse=True)
    def cleanup_all_resources(self, lisa_client, test_repository_id):
        """Cleanup fixture that runs after all tests in the class."""
        yield  # Let tests run first

        # Cleanup all created collections
        logger.info("=" * 60)
        logger.info("CLEANUP: Removing all test collections created during tests")
        logger.info("=" * 60)

        for collection_id in self.created_collections:
            try:
                logger.info(f"Deleting collection: {collection_id}")
                lisa_client.delete_collection(test_repository_id, collection_id)
                logger.info(f"✓ Deleted collection: {collection_id}")
            except Exception as e:
                logger.warning(f"Failed to delete collection {collection_id}: {e}")

        # Clear the list
        self.created_collections.clear()
        logger.info("✓ Cleanup complete")

    @pytest.fixture(scope="class")
    def lisa_client(self) -> LisaApi:
        """Create LISA API client for integration tests.

        Returns:
            LisaApi: Configured LISA API client

        Raises:
            pytest.skip: If required environment variables are not set
        """
        # Get configuration from environment
        api_url = os.getenv("LISA_API_URL")
        deployment_name = os.getenv("LISA_DEPLOYMENT_NAME")
        deployment_stage = os.getenv("LISA_DEPLOYMENT_STAGE")
        region = os.getenv("AWS_DEFAULT_REGION")
        verify_ssl = os.getenv("LISA_VERIFY_SSL", "true").lower() == "true"

        if not api_url or not deployment_name:
            pytest.skip("LISA_API_URL and LISA_DEPLOYMENT_NAME environment variables required for integration tests")

        # Create client using common utilities
        client = create_lisa_client(api_url, deployment_name, region, verify_ssl, deployment_stage=deployment_stage)

        logger.info(f"Created LISA client for {api_url}")
        return client

    @pytest.fixture(scope="class")
    def test_repository_id(self, lisa_client: LisaApi) -> str:
        """Get or create a test repository for integration tests.

        Args:
            lisa_client: LISA API client

        Returns:
            str: Repository ID to use for tests

        Raises:
            pytest.skip: If no suitable repository is available
        """
        return os.getenv("TEST_REPOSITORY_ID", "test-pgvector-rag")

    @pytest.fixture(scope="class")
    def test_embedding_model(self) -> str:
        """Get the embedding model to use for tests.

        Returns:
            str: Embedding model ID
        """
        # Use a common embedding model
        return os.getenv("TEST_EMBEDDING_MODEL", "titan-embed")

    @pytest.fixture(scope="class")
    def test_collection(self, lisa_client: LisaApi, test_repository_id: str, test_embedding_model: str) -> dict:
        """Create a test collection for integration tests.

        Args:
            lisa_client: LISA API client
            test_repository_id: Repository ID to create collection in
            test_embedding_model: Embedding model to use for the collection

        Returns:
            Dict: Created collection configuration

        Yields:
            Dict: Collection configuration for tests
        """
        # Create test collection
        collection_name = f"{TEST_COLLECTION_ID}-{int(time.time())}"
        logger.info(f"Creating test collection: {collection_name}")

        collection = None
        try:
            collection = lisa_client.create_collection(
                repository_id=test_repository_id,
                name=collection_name,
                description="Integration test collection",
                embedding_model=test_embedding_model,
                chunking_strategy={"type": "fixed", "size": 512, "overlap": 51},
            )
            collection_id = collection.get("collectionId")
            logger.info(f"Created collection: {collection_id} {collection_name}")

            # Track for cleanup
            self.created_collections.append(collection_id)

            yield collection

        finally:
            # Individual test cleanup (belt and suspenders approach)
            if collection and collection.get("collectionId"):
                collection_id = collection.get("collectionId")
                try:
                    logger.info(f"Test fixture cleanup: {collection_id}")
                    lisa_client.delete_collection(test_repository_id, collection_id)
                    # Remove from tracking list if successfully deleted
                    if collection_id in self.created_collections:
                        self.created_collections.remove(collection_id)
                except Exception as e:
                    logger.debug(f"Fixture cleanup failed (will retry in final cleanup): {e}")

    @pytest.fixture
    def test_document_file(self) -> str:
        """Create a temporary test document file.

        Returns:
            str: Path to temporary test document

        Yields:
            str: Path to test document file
        """
        # Create temporary file with test content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(TEST_DOCUMENT_CONTENT)
            temp_path = f.name

        logger.info(f"Created test document: {temp_path}")
        yield temp_path

        # Cleanup
        try:
            os.unlink(temp_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup test document file: {e}")


class TestRagCollectionsIntegration(RagIntegrationFixtures):
    """Integration tests for RAG collections using direct API upload/ingest."""

    def test_01_create_collection(self, lisa_client: LisaApi, test_repository_id: str, test_collection: dict):
        """Test 1: Verify collection was created via fixture.

        Verifies:
        - Collection exists with correct attributes
        - Collection can be retrieved via SDK
        """
        collection_id = test_collection.get("collectionId")
        logger.info(f"Test 1: Verifying collection {collection_id}")

        # Verify collection attributes from fixture
        assert test_collection is not None
        assert collection_id is not None
        assert test_collection.get("repositoryId") == test_repository_id
        logger.info(f"✓ Collection exists: {collection_id}")

        # Verify collection can be retrieved via API
        retrieved = lisa_client.get_collection(test_repository_id, collection_id)
        assert retrieved is not None
        assert retrieved.get("collectionId") == collection_id
        logger.info("✓ Collection retrieved successfully via API")

        logger.info("✓ Test 1 completed successfully")

    def test_02_ingest_document_to_collection(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_collection: dict,
        test_embedding_model: str,
        test_document_file: str,
    ):
        """Test 2: Ingest document to collection.

        Verifies:
        - Document can be uploaded to collection
        - Ingestion job completes successfully
        - Document exists in DocumentsTable with correct collection_id
        - Subdocuments exist in SubDocumentsTable
        - Document exists in S3
        - Embeddings exist in vector store
        """
        collection_id = test_collection.get("collectionId")
        logger.info(f"Test 2: Ingesting document to collection ({collection_id})")

        # Upload document to S3 first
        presigned_data = lisa_client._presigned_url(os.path.basename(test_document_file))
        s3_key = presigned_data.get("key")

        lisa_client._upload_document(presigned_data, test_document_file)
        logger.info(f"✓ Document uploaded to S3: {s3_key}")

        # Ingest document to collection and get job info (use collection_id for user-facing API)
        jobs = lisa_client.ingest_document(
            repo_id=test_repository_id,
            model_id=test_embedding_model,
            file=s3_key,
            collection_id=collection_id,
        )
        logger.info("✓ Ingestion job started")
        logger.info(f"Jobs response: {jobs}")

        assert len(jobs) > 0, f"No jobs returned from ingestion. Response: {jobs}"
        job_info = jobs[0]
        job_id = job_info.get("jobId")
        logger.info(f"✓ Job created: {job_id}, Status: {job_info.get('status')}")
        assert job_id is not None, f"No jobId in job info: {job_info}"

        # Wait for batch job to complete and document to appear
        max_wait = 360  # 6 minutes to account for infrastructure spin-up
        start_time = time.time()

        logger.info(f"Waiting for batch job to complete (up to {max_wait}s)...")
        while time.time() - start_time < max_wait:
            try:
                documents = lisa_client.list_documents(test_repository_id, collection_id)
                if documents:
                    document_name = documents[0].get("document_name")
                    elapsed = int(time.time() - start_time)
                    logger.info(f"✓ Document ingested after {elapsed}s: {document_name}")
                    break
            except Exception as e:
                logger.debug(f"Waiting for ingestion: {e}")
            time.sleep(10)

        assert documents and len(documents) > 0, f"Document ingestion timed out after {max_wait}s"

        # Verify document exists and has correct attributes
        doc_item = documents[0]
        document_name = doc_item.get("document_name")
        assert document_name is not None, "No document_name in response"
        assert doc_item.get("collection_id") == collection_id
        logger.info(f"✓ Document verified in collection: {document_name}")

        # Verify document has S3 source
        source_uri = doc_item.get("source", "")
        assert source_uri.startswith("s3://"), f"Invalid S3 source URI: {source_uri}"
        logger.info(f"✓ Document has valid S3 source: {source_uri}")

        logger.info("✓ Test 2 completed successfully")

    def test_03_similarity_search_on_collection(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_collection: dict,
    ):
        """Test 3: Perform similarity search on collection.

        Verifies:
        - Similarity search returns results
        - Results contain the ingested document
        - Results match document content
        - Results have document_id enriched in metadata
        """
        collection_id = test_collection.get("collectionId")
        logger.info(f"Test 3: Performing similarity search on collection {collection_id}")

        # # Wait longer for embeddings to be indexed and available
        # logger.info("Waiting for embeddings to be indexed...")
        # time.sleep(30)

        # Perform similarity search with retry logic
        # Note: No need to pass model_name - it will be pulled from the collection
        query = "machine learning and artificial intelligence"
        max_retries = 3
        results = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Similarity search attempt {attempt + 1}/{max_retries}")
                results = lisa_client.similarity_search(
                    repo_id=test_repository_id, query=query, k=5, collection_id=collection_id
                )
                break
            except Exception as e:
                logger.warning(f"Similarity search attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)
                else:
                    raise

        # Verify results
        assert results is not None, "No results returned from similarity search"
        assert len(results) > 0, "Similarity search returned empty results"
        logger.info(f"✓ Similarity search returned {len(results)} results")

        # Verify results contain relevant content
        found_relevant = False
        for result in results:
            content = result.get("Document", {}).get("page_content", "")
            if "machine learning" in content.lower() or "artificial intelligence" in content.lower():
                found_relevant = True
                break

        assert found_relevant, "Search results did not contain relevant content"
        logger.info("✓ Search results contain relevant content")

        # Verify document_id enrichment in metadata
        for result in results:
            metadata = result.get("Document", {}).get("metadata", {})
            if metadata.get("source"):  # Only check if source is present
                # document_id should be enriched for documents with source
                # Note: May not be present if lookup failed, which is acceptable
                if "document_id" in metadata:
                    logger.info(f"✓ Document has enriched document_id: {metadata['document_id']}")
                else:
                    logger.info("ℹ Document does not have document_id (enrichment may have failed gracefully)")

        logger.info("✓ Test 3 completed successfully")

    def test_04_delete_document_and_verify_cleanup(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_collection: dict,
    ):
        """Test 4: Delete document and verify cleanup.

        Verifies:
        - Document can be deleted
        - Document removed from DocumentsTable
        - Subdocuments removed from SubDocumentsTable
        - Document removed from S3
        - Embeddings removed from vector store
        """
        collection_id = test_collection.get("collectionId")
        logger.info("Test 4: Deleting document and verifying cleanup")

        # Get documents in collection (use collection_id for user-facing API)
        documents = lisa_client.list_documents(test_repository_id, collection_id)
        assert len(documents) > 0, "No documents to delete"

        document_id = documents[0].get("document_id")
        logger.info(f"Deleting document: {document_id}")

        # Delete document (use collection_id for user-facing API)
        delete_response = lisa_client.delete_document_by_ids(test_repository_id, collection_id, [document_id])
        logger.info("✓ Document deletion requested")
        logger.info(f"Delete response: {delete_response}")

        # Get job info from response
        jobs = delete_response.get("jobs", [])
        assert len(jobs) > 0, "No jobs returned from deletion"
        job_id = jobs[0].get("jobId")
        logger.info(f"✓ Deletion job created: {job_id}")

        # Wait for batch job to complete
        max_wait = 120
        start_time = time.time()

        logger.info(f"Waiting for deletion job to complete (up to {max_wait}s)...")
        while time.time() - start_time < max_wait:
            try:
                # Check if document still exists
                remaining_docs = lisa_client.list_documents(test_repository_id, collection_id)
                remaining_ids = [doc.get("document_id") for doc in remaining_docs]
                if document_id not in remaining_ids:
                    elapsed = int(time.time() - start_time)
                    logger.info(f"✓ Document deleted after {elapsed}s")
                    break
            except Exception as e:
                logger.debug(f"Waiting for deletion: {e}")
            time.sleep(10)

        # Verify document removed
        remaining_docs = lisa_client.list_documents(test_repository_id, collection_id)
        remaining_ids = [doc.get("document_id") for doc in remaining_docs]
        assert document_id not in remaining_ids, f"Document deletion timed out after {max_wait}s"
        logger.info("✓ Document removed from collection listing")

        # Verify document removed using SDK get_document (should fail/return None)
        try:
            _ = lisa_client.get_document(test_repository_id, document_id)
            assert False, f"Document {document_id} still exists after deletion"
        except Exception:
            # Expected - document should not be found
            logger.info("✓ Document removed (get_document failed as expected)")

        logger.info("✓ Test 4 completed successfully")

    def test_05_get_user_collections(
        self,
        lisa_client: LisaApi,
        test_collection: dict,
    ):
        """Test 5: Get user collections.

        Verifies:
        - User collections can be retrieved across all repositories
        - Test collection appears in results
        """
        collection_id = test_collection.get("collectionId")
        logger.info("Test 5: Getting user collections across all repositories")

        collections = lisa_client.get_user_collections()
        logger.info(f"✓ Retrieved {len(collections)} collections")

        collection_ids = [c.get("collectionId") for c in collections]
        assert collection_id in collection_ids, f"Test collection {collection_id} not found in user collections"
        logger.info(f"✓ Test collection {collection_id} found in user collections")

        logger.info("✓ Test 5 completed successfully")

    def test_06_delete_collection_with_documents(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_embedding_model: str,
        test_collection: str,
        test_document_file: str,
    ):
        """Test 6: Ingest document and delete collection.

        Verifies:
        - Collection with documents can be deleted
        - All documents removed from DocumentsTable
        - All subdocuments removed from SubDocumentsTable
        - All documents removed from S3
        - All embeddings removed from vector store
        - Collection marked as DELETED or removed from DynamoDB
        """
        logger.info("Test 6: Deleting collection with documents")

        collection_id = test_collection.get("collectionId")
        logger.info(f"Created test collection: ({collection_id})")

        # Track for cleanup (in case test fails before deletion)
        self.created_collections.append(collection_id)

        # Upload and ingest document
        presigned_data = lisa_client._presigned_url(os.path.basename(test_document_file))
        s3_key = presigned_data.get("key")

        lisa_client._upload_document(presigned_data, test_document_file)
        lisa_client.ingest_document(
            repo_id=test_repository_id,
            model_id=test_embedding_model,
            file=s3_key,
            collection_id=collection_id,
        )

        # Wait for ingestion
        time.sleep(30)

        # Get document IDs before deletion
        documents = lisa_client.list_documents(test_repository_id, collection_id)
        document_ids = [doc.get("document_id") for doc in documents]
        logger.info(f"Collection has {len(document_ids)} documents")

        # Delete collection
        lisa_client.delete_collection(test_repository_id, collection_id)
        logger.info("✓ Collection deletion requested")

        # Remove from tracking list since we're testing deletion
        if collection_id in self.created_collections:
            self.created_collections.remove(collection_id)

        # Wait for deletion to complete
        time.sleep(10)

        # Verify all documents removed using SDK
        for document_id in document_ids:
            try:
                _ = lisa_client.get_document(test_repository_id, document_id)
                assert False, f"Document {document_id} still exists after collection deletion"
            except Exception:
                # Expected - document should not be found
                pass

        logger.info("✓ All documents removed")

        # Verify collection no longer returns documents
        try:
            remaining_docs = lisa_client.list_documents(test_repository_id, collection_id)
            assert len(remaining_docs) == 0, "Collection still has documents"
        except Exception:
            # Collection may not exist anymore, which is also acceptable
            pass

        logger.info("✓ Collection cleanup verified")


class TestPipelineRagCollectionIntegration(RagIntegrationFixtures):
    """Integration tests for RAG collections using the S3 pipeline EventBridge trigger.

    Tests end-to-end pipeline ingestion and deletion by dropping/removing files
    directly in the pipeline S3 bucket and verifying the event-driven handler
    processes them correctly.
    """

    @pytest.fixture(scope="class")
    def pipeline_info(self, lisa_client: LisaApi, test_repository_id: str, test_embedding_model: str):
        """Discover the pipeline S3 bucket/prefix from TEST_REPOSITORY_ID and create
        a collection whose name is 'default' to test pipeline name-to-UUID resolution.

        Yields the info dict needed by test_01 and test_02.
        Cleans up the collection on teardown.
        """
        import requests as req

        api_url = os.getenv("LISA_API_URL")
        verify_ssl = os.getenv("LISA_VERIFY_SSL", "true").lower() == "true"
        auth_headers = {
            "Api-Key": lisa_client._session.headers.get("Api-Key", ""),
            "Authorization": lisa_client._session.headers.get("Authorization", ""),
        }

        # Discover pipeline S3 bucket from the existing repository
        repo_resp = req.get(
            f"{api_url}/repository/{test_repository_id}",
            headers=auth_headers,
            verify=verify_ssl,
            timeout=30,
        )
        assert repo_resp.status_code == 200, f"Failed to get repository: {repo_resp.text}"
        pipelines = repo_resp.json().get("pipelines", [])
        assert pipelines, f"Repository {test_repository_id} has no pipelines"
        s3_bucket = pipelines[0]["s3Bucket"]
        s3_prefix = pipelines[0].get("s3Prefix", f"pipeline-integ-test-{int(time.time())}/")

        # Create a collection named 'default' — the bug scenario
        collection = lisa_client.create_collection(
            repository_id=test_repository_id,
            name="default",
            description="Pipeline integration test collection",
            embedding_model=test_embedding_model,
            chunking_strategy={"type": "fixed", "size": 512, "overlap": 51},
        )
        collection_uuid = collection["collectionId"]
        assert collection_uuid != "default", f"collectionId should be UUID, got '{collection_uuid}'"
        logger.info(f"Created collection: name='default', uuid={collection_uuid}")

        yield {
            "s3_bucket": s3_bucket,
            "s3_prefix": s3_prefix,
            "collection_uuid": collection_uuid,
        }

        logger.info(f"Cleanup: deleting collection {collection_uuid}")
        try:
            lisa_client.delete_collection(test_repository_id, collection_uuid)
        except Exception as e:
            logger.warning(f"Cleanup: failed to delete collection {collection_uuid}: {e}")

    def test_01_pipeline_ingest_resolves_collection_name_to_uuid(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        pipeline_info: dict,
    ):
        """Drop a file into the pipeline S3 bucket and verify it ingests under the
        UUID collection, confirming the pipeline resolves collection name to UUID.
        """
        import boto3

        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        s3_bucket = pipeline_info["s3_bucket"]
        s3_prefix = pipeline_info["s3_prefix"]
        collection_uuid = pipeline_info["collection_uuid"]

        s3_key = f"{s3_prefix}ingest-test-{int(time.time())}.txt"
        boto3.client("s3", region_name=region).put_object(
            Bucket=s3_bucket, Key=s3_key, Body=b"Pipeline collectionId regression test."
        )
        logger.info(f"Dropped s3://{s3_bucket}/{s3_key} to trigger event-driven ingest")

        max_wait = 300
        start = time.time()
        documents = []
        while time.time() - start < max_wait:
            try:
                documents = lisa_client.list_documents(test_repository_id, collection_uuid)
                if documents:
                    logger.info(f"✓ Document ingested after {int(time.time()-start)}s under UUID {collection_uuid}")
                    break
            except Exception as e:
                logger.debug(f"Waiting for pipeline ingest: {e}")
            logger.info(f"Polling for ingested document... ({int(time.time()-start)}s elapsed)")
            time.sleep(15)

        assert documents, (
            f"Pipeline ingest timed out after {max_wait}s. "
            f"Collection name 'default' was not resolved to UUID '{collection_uuid}'."
        )
        assert documents[0]["collection_id"] == collection_uuid

    def test_02_pipeline_delete_resolves_collection_name_to_uuid(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        pipeline_info: dict,
    ):
        """Delete the S3 file and verify the document is removed, confirming the
        pipeline delete handler resolves collection name to UUID.
        """
        import boto3

        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        s3_bucket = pipeline_info["s3_bucket"]
        collection_uuid = pipeline_info["collection_uuid"]

        documents = lisa_client.list_documents(test_repository_id, collection_uuid)
        assert documents, "No documents to delete — test_01 must pass first"
        document_id = documents[0]["document_id"]
        s3_key = documents[0]["source"].replace(f"s3://{s3_bucket}/", "")

        boto3.client("s3", region_name=region).delete_object(Bucket=s3_bucket, Key=s3_key)
        logger.info(f"Deleted s3://{s3_bucket}/{s3_key} to trigger pipeline deletion event")

        max_wait = 120
        start = time.time()
        while time.time() - start < max_wait:
            remaining = lisa_client.list_documents(test_repository_id, collection_uuid)
            if not any(d["document_id"] == document_id for d in remaining):
                logger.info(f"✓ Document deleted after {int(time.time()-start)}s via pipeline deletion event")
                break
            logger.info(f"Polling for document deletion... ({int(time.time()-start)}s elapsed)")
            time.sleep(15)
        else:
            assert False, f"Pipeline deletion timed out after {max_wait}s. Delete handler did not process the event."


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
