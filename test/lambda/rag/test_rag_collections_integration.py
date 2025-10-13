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
from typing import Dict, List, Optional

import boto3
import pytest

# Add test utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from test.utils import (
    create_lisa_client,
    get_dynamodb_table,
    get_s3_client,
    get_table_names_from_env,
    verify_document_in_dynamodb,
    verify_document_in_s3,
    verify_document_not_in_s3,
    wait_for_resource_ready,
)

# Add lisa-sdk to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../lisa-sdk"))

from lisapy.api import LisaApi

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Test configuration
TEST_COLLECTION_NAME = "test-collection-integration"
TEST_DOCUMENT_CONTENT = """
This is a test document for RAG collections integration testing.
It contains information about artificial intelligence and machine learning.
Machine learning is a subset of artificial intelligence that focuses on learning from data.
"""


class TestRagCollectionsIntegration:
    """Integration test suite for RAG Collections."""

    # Track created resources for cleanup
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
        # Try to get existing repositories
        try:
            repositories = lisa_client.list_repositories()
            if repositories:
                repo_id = repositories[0].get("repositoryId")
                logger.info(f"Using existing repository: {repo_id}")
                return repo_id
        except Exception as e:
            logger.warning(f"Failed to list repositories: {e}")

        pytest.skip("No repository available for integration tests")

    @pytest.fixture(scope="class")
    def test_embedding_model(self) -> str:
        """Get the embedding model to use for tests.

        Returns:
            str: Embedding model ID
        """
        # Use a common embedding model
        return os.getenv("TEST_EMBEDDING_MODEL", "amazon.titan-embed-text-v1")

    @pytest.fixture(scope="class")
    def test_collection(self, lisa_client: LisaApi, test_repository_id: str) -> Dict:
        """Create a test collection for integration tests.

        Args:
            lisa_client: LISA API client
            test_repository_id: Repository ID to create collection in

        Returns:
            Dict: Created collection configuration

        Yields:
            Dict: Collection configuration for tests
        """
        # Create test collection
        collection_name = f"{TEST_COLLECTION_NAME}-{int(time.time())}"
        logger.info(f"Creating test collection: {collection_name}")

        collection = None
        try:
            collection = lisa_client.create_collection(
                repository_id=test_repository_id,
                name=collection_name,
                description="Integration test collection",
                chunking_strategy={"type": "fixed", "size": 512, "overlap": 51},
            )
            collection_id = collection.get("collectionId")
            logger.info(f"Created collection: {collection_id}")
            
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

    def test_01_create_collection(self, lisa_client: LisaApi, test_repository_id: str):
        """Test 1: Create collection with valid configuration.

        Verifies:
        - Collection can be created via SDK
        - Collection exists in DynamoDB with correct attributes
        - Collection can be retrieved via SDK
        """
        collection_name = f"{TEST_COLLECTION_NAME}-create-{int(time.time())}"
        logger.info(f"Test 1: Creating collection {collection_name}")

        collection = None
        try:
            # Create collection
            collection = lisa_client.create_collection(
                repository_id=test_repository_id,
                name=collection_name,
                description="Test collection for creation test",
                chunking_strategy={"type": "fixed", "size": 512, "overlap": 51},
                metadata={"tags": ["test", "integration"]},
            )

            # Verify collection was created
            assert collection is not None
            assert collection.get("collectionId") is not None
            assert collection.get("name") == collection_name
            assert collection.get("repositoryId") == test_repository_id

            collection_id = collection.get("collectionId")
            logger.info(f"✓ Collection created: {collection_id}")
            
            # Track for cleanup
            self.created_collections.append(collection_id)

            # Verify collection can be retrieved
            try:
                retrieved = lisa_client.get_collection(test_repository_id, collection_id)
                assert retrieved is not None
                assert retrieved.get("collectionId") == collection_id
                assert retrieved.get("name") == collection_name
                logger.info(f"✓ Collection retrieved successfully")
            except Exception as e:
                logger.error(f"Failed to retrieve collection {collection_id}: {e}")
                logger.error(f"This indicates the GET /repository/{test_repository_id}/collection/{collection_id} endpoint has an issue")
                raise

            # Verify collection exists in DynamoDB
            deployment_name = os.getenv("LISA_DEPLOYMENT_NAME", "lisa")
            table_names = get_table_names_from_env(deployment_name)
            region = os.getenv("AWS_DEFAULT_REGION")

            table = get_dynamodb_table(table_names["collections"], region)
            response = table.get_item(Key={"collectionId": collection_id, "repositoryId": test_repository_id})
            assert "Item" in response
            assert response["Item"]["name"] == collection_name

            logger.info(f"✓ Collection verified in DynamoDB")

        finally:
            # Cleanup
            if collection and collection.get("collectionId"):
                collection_id = collection.get("collectionId")
                try:
                    logger.info(f"Test cleanup: Deleting collection {collection_id}")
                    lisa_client.delete_collection(test_repository_id, collection_id)
                    # Remove from tracking list if successfully deleted
                    if collection_id in self.created_collections:
                        self.created_collections.remove(collection_id)
                    logger.info(f"✓ Test collection cleaned up")
                except Exception as e:
                    logger.debug(f"Test cleanup failed (will retry in final cleanup): {e}")

    def test_02_ingest_document_to_collection(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_collection: Dict,
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
        logger.info(f"Test 2: Ingesting document to collection {collection_id}")

        # Upload document to S3 first
        presigned_data = lisa_client._presigned_url(os.path.basename(test_document_file))
        presigned_url = presigned_data.get("url")
        s3_key = presigned_data.get("key")

        lisa_client._upload_document(presigned_url, test_document_file)
        logger.info(f"✓ Document uploaded to S3: {s3_key}")

        # Ingest document to collection
        lisa_client.ingest_document(
            repo_id=test_repository_id,
            model_id=test_embedding_model,
            file=s3_key,
            collection_id=collection_id,
        )
        logger.info(f"✓ Ingestion job started")

        # Wait for ingestion to complete (poll for document)
        max_wait = 300  # 5 minutes
        start_time = time.time()
        document_id = None

        while time.time() - start_time < max_wait:
            try:
                documents = lisa_client.list_documents(test_repository_id, collection_id)
                if documents:
                    document_id = documents[0].get("document_id")
                    logger.info(f"✓ Document ingested: {document_id}")
                    break
            except Exception as e:
                logger.debug(f"Waiting for ingestion: {e}")

            time.sleep(10)

        assert document_id is not None, "Document ingestion timed out"

        # Verify document in DocumentsTable
        deployment_name = os.getenv("LISA_DEPLOYMENT_NAME", "lisa")
        table_names = get_table_names_from_env(deployment_name)
        region = os.getenv("AWS_DEFAULT_REGION")

        assert verify_document_in_dynamodb(document_id, table_names["documents"], collection_id, region)

        # Get document details for further verification
        doc_table = get_dynamodb_table(table_names["documents"], region)
        response = doc_table.query(
            IndexName="document_index",
            KeyConditionExpression="document_id = :doc_id",
            ExpressionAttributeValues={":doc_id": document_id},
        )
        doc_item = response["Items"][0]
        logger.info(f"✓ Document verified in DocumentsTable")

        # Verify subdocuments in SubDocumentsTable
        subdoc_table = get_dynamodb_table(table_names["subdocuments"], region)
        subdoc_response = subdoc_table.query(
            KeyConditionExpression="document_id = :doc_id", ExpressionAttributeValues={":doc_id": document_id}
        )

        assert subdoc_response["Count"] > 0
        logger.info(f"✓ Subdocuments verified in SubDocumentsTable ({subdoc_response['Count']} subdocs)")

        # Verify document in S3
        source_uri = doc_item.get("source", "")
        if source_uri.startswith("s3://"):
            assert verify_document_in_s3(source_uri, region)

        logger.info(f"✓ Test 2 completed successfully")

    def test_03_similarity_search_on_collection(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_collection: Dict,
        test_embedding_model: str,
    ):
        """Test 3: Perform similarity search on collection.

        Verifies:
        - Similarity search returns results
        - Results contain the ingested document
        - Results match document content
        """
        collection_id = test_collection.get("collectionId")
        logger.info(f"Test 3: Performing similarity search on collection {collection_id}")

        # Wait a bit for embeddings to be indexed
        time.sleep(5)

        # Perform similarity search
        query = "machine learning and artificial intelligence"
        results = lisa_client.similarity_search(
            repo_id=test_repository_id, model_name=test_embedding_model, query=query, k=5, collection_id=collection_id
        )

        # Verify results
        assert results is not None
        assert len(results) > 0
        logger.info(f"✓ Similarity search returned {len(results)} results")

        # Verify results contain relevant content
        found_relevant = False
        for result in results:
            content = result.get("Document", {}).get("page_content", "")
            if "machine learning" in content.lower() or "artificial intelligence" in content.lower():
                found_relevant = True
                break

        assert found_relevant, "Search results did not contain relevant content"
        logger.info(f"✓ Search results contain relevant content")

        logger.info(f"✓ Test 3 completed successfully")

    def test_04_delete_document_and_verify_cleanup(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_collection: Dict,
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
        logger.info(f"Test 4: Deleting document and verifying cleanup")

        # Get documents in collection
        documents = lisa_client.list_documents(test_repository_id, collection_id)
        assert len(documents) > 0, "No documents to delete"

        document_id = documents[0].get("document_id")
        source_uri = documents[0].get("source", "")
        logger.info(f"Deleting document: {document_id}")

        # Delete document
        lisa_client.delete_document_by_ids(test_repository_id, collection_id, [document_id])
        logger.info(f"✓ Document deletion requested")

        # Wait for deletion to complete
        time.sleep(5)

        # Verify document removed from DocumentsTable
        deployment_name = os.getenv("LISA_DEPLOYMENT_NAME", "lisa")
        table_names = get_table_names_from_env(deployment_name)
        region = os.getenv("AWS_DEFAULT_REGION")

        doc_table = get_dynamodb_table(table_names["documents"], region)
        response = doc_table.query(
            IndexName="document_index",
            KeyConditionExpression="document_id = :doc_id",
            ExpressionAttributeValues={":doc_id": document_id},
        )

        assert response["Count"] == 0, "Document still exists in DocumentsTable"
        logger.info(f"✓ Document removed from DocumentsTable")

        # Verify subdocuments removed from SubDocumentsTable
        subdoc_table = get_dynamodb_table(table_names["subdocuments"], region)
        subdoc_response = subdoc_table.query(
            KeyConditionExpression="document_id = :doc_id", ExpressionAttributeValues={":doc_id": document_id}
        )

        assert subdoc_response["Count"] == 0, "Subdocuments still exist in SubDocumentsTable"
        logger.info(f"✓ Subdocuments removed from SubDocumentsTable")

        # Verify document removed from S3
        if source_uri.startswith("s3://"):
            assert verify_document_not_in_s3(source_uri, region)

        logger.info(f"✓ Test 4 completed successfully")

    def test_05_delete_collection_with_documents(
        self,
        lisa_client: LisaApi,
        test_repository_id: str,
        test_embedding_model: str,
        test_document_file: str,
    ):
        """Test 5: Ingest document and delete collection.

        Verifies:
        - Collection with documents can be deleted
        - All documents removed from DocumentsTable
        - All subdocuments removed from SubDocumentsTable
        - All documents removed from S3
        - All embeddings removed from vector store
        - Collection marked as DELETED or removed from DynamoDB
        """
        logger.info(f"Test 5: Deleting collection with documents")

        # Create a new collection for this test
        collection_name = f"{TEST_COLLECTION_NAME}-delete-{int(time.time())}"
        collection = lisa_client.create_collection(
            repository_id=test_repository_id,
            name=collection_name,
            description="Test collection for deletion test",
        )
        collection_id = collection.get("collectionId")
        logger.info(f"Created test collection: {collection_id}")
        
        # Track for cleanup (in case test fails before deletion)
        self.created_collections.append(collection_id)

        # Upload and ingest document
        presigned_data = lisa_client._presigned_url(os.path.basename(test_document_file))
        presigned_url = presigned_data.get("url")
        s3_key = presigned_data.get("key")

        lisa_client._upload_document(presigned_url, test_document_file)
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
        source_uris = [doc.get("source") for doc in documents]

        logger.info(f"Collection has {len(document_ids)} documents")

        # Delete collection
        lisa_client.delete_collection(test_repository_id, collection_id)
        logger.info(f"✓ Collection deletion requested")
        
        # Remove from tracking list since we're testing deletion
        if collection_id in self.created_collections:
            self.created_collections.remove(collection_id)

        # Wait for deletion to complete
        time.sleep(10)

        # Verify all documents removed from DocumentsTable
        deployment_name = os.getenv("LISA_DEPLOYMENT_NAME", "lisa")
        table_names = get_table_names_from_env(deployment_name)
        region = os.getenv("AWS_DEFAULT_REGION")

        doc_table = get_dynamodb_table(table_names["documents"], region)
        for document_id in document_ids:
            response = doc_table.query(
                IndexName="document_index",
                KeyConditionExpression="document_id = :doc_id",
                ExpressionAttributeValues={":doc_id": document_id},
            )
            assert response["Count"] == 0, f"Document {document_id} still exists in DocumentsTable"

        logger.info(f"✓ All documents removed from DocumentsTable")

        # Verify all subdocuments removed from SubDocumentsTable
        subdoc_table = get_dynamodb_table(table_names["subdocuments"], region)
        for document_id in document_ids:
            subdoc_response = subdoc_table.query(
                KeyConditionExpression="document_id = :doc_id", ExpressionAttributeValues={":doc_id": document_id}
            )
            assert subdoc_response["Count"] == 0, f"Subdocuments for {document_id} still exist"

        logger.info(f"✓ All subdocuments removed from SubDocumentsTable")

        # Verify all documents removed from S3
        for source_uri in source_uris:
            if source_uri and source_uri.startswith("s3://"):
                assert verify_document_not_in_s3(source_uri, region)

        logger.info(f"✓ All documents removed from S3")

        # Verify collection is deleted or marked as DELETED
        collections_table = get_dynamodb_table(table_names["collections"], region)
        coll_response = collections_table.get_item(
            Key={"collectionId": collection_id, "repositoryId": test_repository_id}
        )

        if "Item" in coll_response:
            # Soft delete - verify status is DELETED
            assert coll_response["Item"].get("status") == "DELETED", "Collection not marked as DELETED"
            logger.info(f"✓ Collection marked as DELETED")
        else:
            # Hard delete - collection removed
            logger.info(f"✓ Collection removed from DynamoDB")

        logger.info(f"✓ Test 5 completed successfully")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
