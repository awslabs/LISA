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
from typing import Optional, TypeAlias

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from models.domain_objects import RagDocument, RagSubDocument

logger = logging.getLogger(__name__)

MAX_SUBDOCS = 1000

RagDocumentDict: TypeAlias = RagDocument.model_dump
RagSubDocumentDict: TypeAlias = RagSubDocument.model_dump


class RagDocumentRepository:
    """RAG Document repository for DynamoDB"""

    def __init__(self, document_table_name: str, sub_document_table_name: str):
        self.dynamodb = boto3.resource("dynamodb")
        self.doc_table = self.dynamodb.Table(document_table_name)
        self.subdoc_table = self.dynamodb.Table(sub_document_table_name)

    def delete_by_id(self, repository_id: str, document_id: str) -> None:
        """Delete a document using partition key and sort key.

        Args:
            pk: Partition key value
            document_id: Sort key value

        Returns:
            Dict containing the response from DynamoDB

        Raises:
            ClientError: If deletion fails
        """
        try:
            document = self.find_by_id(repository_id=repository_id, document_id=document_id)
            subdocs = self.find_subdocs_by_id(document_id)

            with self.subdoc_table.batch_writer() as batch:
                for doc in subdocs:
                    batch.delete_item(Key={"document_id": doc["document_id"], "sk": doc["sk"]})

            self.doc_table.delete_item(Key={"pk": document["pk"], "document_id": document["document_id"]})
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

    def find_by_id(self, repository_id: str, document_id: str, join_docs: bool = False) -> RagDocumentDict:
        """Query documents using GSI.

        Args:
            document_id: Document ID to query
            index_name: Name of the GSI
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
                FilterExpression="repository_id = :repository_id",
                ExpressionAttributeValues={":document_id": document_id, ":repository_id": repository_id},
            )
            docs: list[RagDocumentDict] = response.get("Items", [])
            # Handle paginated Dynamo results
            while "LastEvaluatedKey" in response:
                response = self.doc_table.query(
                    IndexName="document_index",
                    KeyConditionExpression="document_id = :document_id",
                    FilterExpression="repository_id = :repository_id",
                    ExpressionAttributeValues={":document_id": document_id, ":repository_id": repository_id},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                docs.extend(response["Items"])
            if not docs:
                raise ValueError(f"Document not found for document_id {document_id}")
            if join_docs:
                subdocs = RagDocumentRepository._get_subdoc_ids(self.find_subdocs_by_id(document_id))
                docs[0]["subdocs"] = subdocs
            return docs[0]
        except ClientError as e:
            logging.error(f"Error querying document: {e.response['Error']['Message']}")
            raise

    def find_by_name(
        self, repository_id: str, collection_id: str, document_name: str, join_docs: bool = False
    ) -> list[RagDocumentDict]:
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
        docs: list[RagDocumentDict] = response["Items"]

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
                subdocs = RagDocumentRepository._get_subdoc_ids(self.find_subdocs_by_id(doc.get("document_id")))
                doc["subdocs"] = subdocs
        return docs

    def list_all(
        self,
        repository_id: str,
        collection_id: Optional[str],
        last_evaluated_key: Optional[dict] = None,
        limit: int = 100,
        join_docs: bool = False,
    ) -> tuple[list[RagDocumentDict], Optional[dict]]:
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

            docs: list[RagDocumentDict] = response.get("Items", [])
            next_key = response.get("LastEvaluatedKey", None)

            if join_docs:
                for doc in docs:
                    subdocs = RagDocumentRepository._get_subdoc_ids(self.find_subdocs_by_id(doc.get("document_id")))
                    doc["subdocs"] = subdocs

            return docs, next_key

        except ClientError as e:
            logging.error(f"Error listing documents: {e.response['Error']['Message']}")
            raise

    def find_subdocs_by_id(self, document_id: str) -> list[RagSubDocumentDict]:
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
            entries: list[RagDocumentDict] = response.get("Items", [])
            # Handle paginated Dynamo results
            while "LastEvaluatedKey" in response:
                response = self.subdoc_table.query(
                    KeyConditionExpression=Key("document_id").eq(document_id),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                entries.extend(response["Items"])
            return entries
        except ClientError as e:
            logging.error(f"Error querying subdocuments: {e.response['Error']['Message']}")
            raise

    @staticmethod
    def _get_subdoc_ids(entries: RagSubDocumentDict) -> list[str]:
        """Map subdocuments from a document object.

        Args:
            document: The document object containing subdocuments

        Returns:
            List of subdocument dictionaries
        """
        return [doc for entry in entries for doc in entry["subdocs"]]
