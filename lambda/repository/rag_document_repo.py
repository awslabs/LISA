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
import logging
import os
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import Generator, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from models.domain_objects import IngestionType, RagDocument, RagSubDocument
from repository.vector_store_repo import VectorStoreRepository

logger = logging.getLogger(__name__)

MAX_SUBDOCS = 1000


class RagDocumentRepository:
    """RAG Document repository for DynamoDB"""

    def __init__(self, document_table_name: str, sub_document_table_name: str):
        dynamodb = boto3.resource("dynamodb")
        self.doc_table = dynamodb.Table(document_table_name)
        self.subdoc_table = dynamodb.Table(sub_document_table_name)
        self.s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"])
        self.vs_repo = VectorStoreRepository()

    def delete_by_id(self, document_id: str) -> None:
        """Delete a document using partition key and sort key.

        Args:
            pk: Partition key value
            document_id: Sort key value

        Returns:
            Dict containing the response from DynamoDB

        Raises:
            ClientError: If deletion fails
        """
        logging.info(f"Removing document {document_id}")
        try:
            document = self.find_by_id(document_id)
            subdocs = self.find_subdocs_by_id(document_id)
            print(f"delete_by_id({document_id}) - {document}[subdocs={subdocs}]")

            with self.subdoc_table.batch_writer() as batch:
                for doc in subdocs:
                    batch.delete_item(Key={"document_id": doc.document_id, "sk": doc.sk})

            # Check if document exists before trying to delete it
            if document is not None:
                self.doc_table.delete_item(Key={"pk": document.pk, "document_id": document.document_id})
            else:
                logging.warning(f"Document with ID {document_id} not found, skipping deletion from doc table")
        except ClientError as e:
            logging.error(f"Error deleting document: {e.response['Error']['Message']}")
            raise

    def save(self, document: RagDocument) -> None:
        """Save a document to DynamoDB.

        Args:
            document: Dictionary containing document attributes

        Returns:
            Dict containing the response from DynamoDB

        Raises:
            ClientError: If save operation fails
        """
        try:
            chunked_docs = list(document.chunk_doc(chunk_size=MAX_SUBDOCS))
            # Save document to metadata table
            self.doc_table.put_item(Item=document.model_dump())
            # Save subdocs to separate table
            with self.subdoc_table.batch_writer() as batch:
                for chunk in chunked_docs:
                    batch.put_item(Item=chunk.model_dump())

        except ClientError as e:
            logging.error(f"Error saving document: {e.response['Error']['Message']}")
            raise

    def find_by_id(self, document_id: str, join_docs: bool = False) -> Optional[RagDocument]:
        """Query documents using GSI.

        Args:
            document_id: Document ID to query
            join_docs: Join document entries together if record is chunked
        Returns:
            List of matching documents

        Raises:
            ClientError: If query operation fails
        """
        try:
            response = self.doc_table.query(
                IndexName="document_index",
                KeyConditionExpression="document_id = :document_id",
                ExpressionAttributeValues={":document_id": document_id},
            )
            docs: list[RagDocument] = response.get("Items", [])

            if not docs:
                logging.warning(f"Document not found for document_id {document_id}")
                return None

            if join_docs:
                subdocs = self._get_subdoc_ids(self.find_subdocs_by_id(document_id))
                docs[0]["subdocs"] = subdocs

            doc = RagDocument(**docs[0])
            return doc
        except ClientError as e:
            logging.error(f"Error querying document: {e.response['Error']['Message']}")
            raise

    def find_by_name(
        self, repository_id: str, collection_id: str, document_name: str, join_docs: bool = False
    ) -> list[RagDocument]:
        """Get a list of documents from the RagDocTable by name.

        Args:
            document_name (str): The name of the documents to retrieve
            repository_id (str): The repository id to list documents for
            collection_id (str): The collection id to list documents for

        Returns:
            list[RagDocument]: A list of document objects matching the specified name

        Raises:
            KeyError: If no documents are found with the specified name
        """
        pk = RagDocument.createPartitionKey(repository_id, collection_id)
        response = self.doc_table.query(
            KeyConditionExpression=Key("pk").eq(pk), FilterExpression=Key("document_name").eq(document_name)
        )
        docs: list[RagDocument] = response["Items"]

        # Handle paginated Dynamo results
        while "LastEvaluatedKey" in response:
            response = self.doc_table.query(
                KeyConditionExpression=Key("pk").eq(pk),
                FilterExpression=Key("document_name").eq(document_name),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            docs.extend(response["Items"])

        if join_docs:
            for doc in docs:
                subdocs = self._get_subdoc_ids(self.find_subdocs_by_id(doc.get("document_id")))
                doc["subdocs"] = subdocs
        return docs

    def find_by_source(
        self, repository_id: str, collection_id: str, document_source: str, join_docs: bool = False
    ) -> Generator[RagDocument, None, None]:
        """Get a list of documents from the RagDocTable by source.

        Args:
            document_source (str): The name of the documents to retrieve
            repository_id (str): The repository id to list documents for

        Returns:
            list[RagDocument]: A list of document objects matching the specified name

        Raises:
            KeyError: If no documents are found with the specified name
        """
        pk = RagDocument.createPartitionKey(repository_id, collection_id)
        response = self.doc_table.query(
            KeyConditionExpression=Key("pk").eq(pk), FilterExpression=Key("source").eq(document_source)
        )

        items = response["Items"]
        logging.info(f"response items: {items}")
        yield from self._yield_documents(response["Items"], join_docs=join_docs)

        # Handle paginated Dynamo results
        while "LastEvaluatedKey" in response:
            response = self.doc_table.query(
                KeyConditionExpression=Key("pk").eq(pk),
                FilterExpression=Key("document_name").eq(document_source),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )

            yield from self._yield_documents(response["Items"], join_docs=join_docs)

    def _yield_documents(self, items: list[dict], join_docs: bool) -> Generator[RagDocument, None, None]:
        for item in items:
            document = RagDocument(**item)
            if join_docs:
                document.subdocs = self._get_subdoc_ids(self.find_subdocs_by_id(document.document_id))
            yield document

    def list_all(
        self,
        repository_id: str,
        collection_id: Optional[str] = None,
        last_evaluated_key: Optional[dict] = None,
        limit: int = 100,
        join_docs: bool = False,
    ) -> tuple[list[RagDocument], Optional[dict], int]:
        """List all documents in a collection.

        Args:
            repository_id: Repository ID
            collection_id?: Collection ID
            last_evaluated_key: last key for pagination
            limit: maximum returned items
            join_docs: whether to include subdoc ids with parent doc
        Returns:
            List of documents
        """
        try:
            response = None
            # Find all rag documents using repo id only
            if not collection_id:
                query_params = {
                    "IndexName": "repository_index",
                    "KeyConditionExpression": Key("repository_id").eq(repository_id),
                    "Limit": limit,
                }
                if last_evaluated_key:
                    query_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.doc_table.query(**query_params)
            # Find all rag documents using repo id and collection
            else:
                pk = RagDocument.createPartitionKey(repository_id, collection_id)
                query_params = {"KeyConditionExpression": Key("pk").eq(pk), "Limit": limit}
                if last_evaluated_key:
                    query_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.doc_table.query(**query_params)

            docs: list[RagDocument] = [RagDocument(**item) for item in response.get("Items", [])]
            next_key = response.get("LastEvaluatedKey", None)

            if join_docs:
                for doc in docs:
                    subdocs = self._get_subdoc_ids(self.find_subdocs_by_id(doc.document_id))
                    doc.subdocs = subdocs

            total_documents = self.count_documents(repository_id=repository_id, collection_id=collection_id)

            return docs, next_key, total_documents

        except ClientError as e:
            logging.error(f"Error listing documents: {e.response['Error']['Message']}")
            raise

    def count_documents(self, repository_id: str, collection_id: Optional[str] = None) -> int:
        """Count total documents in a repository/collection.
        Args:
            repository_id: Repository ID
            collection_id?: Collection ID
        Returns:
            Total number of documents
        """
        count = 0
        # Count all rag documents using repo id only
        if not collection_id:
            response = self.doc_table.query(
                IndexName="repository_index",
                KeyConditionExpression=Key("repository_id").eq(repository_id),
                Select="COUNT",
            )
            count = response.get("Count", 0)
        else:
            pk = RagDocument.createPartitionKey(repository_id, collection_id)
            response = self.doc_table.query(KeyConditionExpression=Key("pk").eq(pk), Select="COUNT")
            count = response.get("Count", 0)
        return count

    def find_subdocs_by_id(self, document_id: str) -> list[RagSubDocument]:
        """Query subdocuments using GSI.

        Args:
            document_id: Document ID to query

        Returns:
            List of matching subdocuments

        Raises:
            ClientError: If query operation fails
        """
        try:
            response = self.subdoc_table.query(
                KeyConditionExpression=Key("document_id").eq(document_id),
            )
            entries: list[RagSubDocument] = response.get("Items", [])
            # Handle paginated Dynamo results
            while "LastEvaluatedKey" in response:
                response = self.subdoc_table.query(
                    KeyConditionExpression=Key("document_id").eq(document_id),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                entries.extend(response["Items"])

            return [RagSubDocument(**entry) for entry in entries]
        except ClientError as e:
            logging.error(f"Error querying subdocuments: {e.response['Error']['Message']}")
            raise

    def _get_subdoc_ids(self, entries: list[RagSubDocument]) -> list[str]:
        """Map subdocuments from a document object.

        Args:
            document: The document object containing subdocuments

        Returns:
            List of subdocument dictionaries
        """
        return [doc for entry in entries for doc in entry.subdocs]

    def delete_s3_object(self, uri: str) -> None:
        """Delete an object and its metadata file from S3.

        Args:
            uri: The S3 URI of the object to delete (s3://bucket/key)
        """
        try:
            bucket, key = uri.replace("s3://", "").split("/", 1)

            # Delete document
            logging.info(f"Deleting S3 object: {bucket}/{key}")
            self.s3_client.delete_object(Bucket=bucket, Key=key)

            # Delete metadata file
            metadata_key = f"{key}.metadata.json"
            try:
                logging.info(f"Deleting metadata file: {bucket}/{metadata_key}")
                self.s3_client.delete_object(Bucket=bucket, Key=metadata_key)
            except ClientError as e:
                # Metadata file may not exist (idempotent)
                if e.response["Error"]["Code"] != "NoSuchKey":
                    logging.warning(f"Failed to delete metadata file: {e}")

        except ClientError as e:
            logging.error(f"Error deleting S3 object: {e.response['Error']['Message']}")
            raise

    def delete_all(self, repository_id: str, collection_id: str) -> None:
        """Delete all documents and subdocuments for a collection.

        Args:
            repository_id: Repository ID
            collection_id: Collection ID
        """
        pk = RagDocument.createPartitionKey(repository_id, collection_id)
        doc_ids = []

        # Query and delete documents, collecting doc_ids in single pass
        response = self.doc_table.query(KeyConditionExpression=Key("pk").eq(pk), ProjectionExpression="pk,document_id")
        with self.doc_table.batch_writer() as batch:
            for item in response["Items"]:
                doc_ids.append(item["document_id"])
                batch.delete_item(Key={"pk": item["pk"], "document_id": item["document_id"]})

        while "LastEvaluatedKey" in response:
            response = self.doc_table.query(
                KeyConditionExpression=Key("pk").eq(pk),
                ProjectionExpression="pk,document_id",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            with self.doc_table.batch_writer() as batch:
                for item in response["Items"]:
                    doc_ids.append(item["document_id"])
                    batch.delete_item(Key={"pk": item["pk"], "document_id": item["document_id"]})

        # Delete subdocuments in parallel
        def delete_subdocs(doc_id: str) -> None:
            response = self.subdoc_table.query(
                KeyConditionExpression=Key("document_id").eq(doc_id), ProjectionExpression="document_id,sk"
            )
            with self.subdoc_table.batch_writer() as batch:
                for item in response["Items"]:
                    batch.delete_item(Key={"document_id": item["document_id"], "sk": item["sk"]})
            while "LastEvaluatedKey" in response:
                response = self.subdoc_table.query(
                    KeyConditionExpression=Key("document_id").eq(doc_id),
                    ProjectionExpression="document_id,sk",
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                with self.subdoc_table.batch_writer() as batch:
                    for item in response["Items"]:
                        batch.delete_item(Key={"document_id": item["document_id"], "sk": item["sk"]})

        if doc_ids:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(delete_subdocs, doc_id) for doc_id in doc_ids]
                for future in as_completed(futures):
                    future.result()

    def delete_s3_docs(self, repository_id: str, docs: list[RagDocument]) -> list[str]:
        """Remove documents from S3 based on ingestion type.

        Only deletes S3 objects for MANUAL and AUTO ingestion types.
        EXISTING documents are preserved in S3 (user-managed).

        Args:
            repository_id: The repository ID
            docs: List of RagDocument objects

        Returns:
            List of S3 URIs that were removed
        """
        repo = self.vs_repo.find_repository_by_id(repository_id=repository_id)

        # Build mapping of collection IDs to autoRemove setting
        collection_auto_remove = {}
        for pipeline in repo.get("pipelines", []):
            embedding_model = pipeline.get("embeddingModel")
            auto_remove = pipeline.get("autoRemove", False) is True
            if embedding_model:
                collection_auto_remove[embedding_model] = auto_remove

        # Determine which documents should be removed from S3
        removed_source: list[str] = []
        preserved_count = 0

        for doc in docs:
            if not doc:
                continue

            doc_source = doc.source
            doc_ingestion_type = doc.ingestion_type
            doc_collection_id = doc.collection_id

            if not doc_source:
                continue

            # EXISTING documents: never remove from S3 (user-managed)
            if doc_ingestion_type == IngestionType.EXISTING:
                logging.info(f"Preserving user-managed document in S3: {doc_source}")
                preserved_count += 1
                continue

            # MANUAL ingestion: always remove from S3
            if doc_ingestion_type == IngestionType.MANUAL:
                removed_source.append(doc_source)
                continue

            # AUTO ingestion: only remove if pipeline exists and has autoRemove enabled
            if doc_ingestion_type == IngestionType.AUTO:
                auto_remove = collection_auto_remove.get(doc_collection_id, False)
                if auto_remove:
                    removed_source.append(doc_source)
                else:
                    logging.info(f"Preserving AUTO document (autoRemove=False or no pipeline): {doc_source}")
                    preserved_count += 1

        # Delete from S3
        for source in removed_source:
            try:
                logging.info(f"Removing S3 doc: {source}")
                self.delete_s3_object(uri=source)
            except Exception as e:
                logging.error(f"Failed to delete S3 object {source}: {e}")
                # Continue with other deletions

        logging.info(f"S3 deletion complete: deleted={len(removed_source)}, preserved={preserved_count}")

        return removed_source
