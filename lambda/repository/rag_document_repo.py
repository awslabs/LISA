import boto3
import logging
from botocore.exceptions import ClientError
from typing import Dict, Any, List, Optional
from enum import Enum
from boto3.dynamodb.conditions import Key

from models.domain_objects import RagDocument

logger = logging.getLogger(__name__)

class RagDocumentRepository:
    """RAG Document repository for DynamoDB"""

    def __init__(self, table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    def delete(self, pk: str, document_id: str) -> Dict[str, Any]:
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
            response = self.table.delete_item(
                Key={
                    'pk': pk,
                    'document_id': document_id
                }
            )
            return response
        except ClientError as e:
            print(f"Error deleting document: {e.response['Error']['Message']}")
            raise

    def batch_delete(self, items: List[Dict[str, str]]) -> None:
        """Delete multiple documents in a batch.

        Args:
            items: List of dictionaries containing pk and document_id pairs

        Raises:
            ClientError: If batch deletion fails
        """
        try:
            with self.table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(
                        Key={
                            'pk': item['pk'],
                            'document_id': item['document_id']
                        }
                    )
        except ClientError as e:
            print(f"Error in batch deletion: {e.response['Error']['Message']}")
            raise

    def save(self, document: RagDocument) -> RagDocument:
        """Save a document to DynamoDB.

        Args:
            document: Dictionary containing document attributes

        Returns:
            Dict containing the response from DynamoDB

        Raises:
            ClientError: If save operation fails
        """
        try:
            response = self.table.put_item(Item=document.dict())
            return response
        except ClientError as e:
            print(f"Error saving document: {e.response['Error']['Message']}")
            raise

    def batch_save(self, documents: List[RagDocument]) -> None:
        """Save multiple documents in a batch.

        Args:
            documents: List of document dictionaries

        Raises:
            ClientError: If batch save operation fails
        """
        try:
            with self.table.batch_writer() as batch:
                for doc in documents:
                    batch.put_item(Item=doc.dict())
        except ClientError as e:
            print(f"Error in batch save: {e.response['Error']['Message']}")
            raise

    def find_by_id(self, document_id: str) -> List[RagDocument]:
        """Query documents using GSI.

        Args:
            document_id: Document ID to query
            index_name: Name of the GSI

        Returns:
            List of matching documents

        Raises:
            ClientError: If query operation fails
        """
        try:
            response = self.table.query(
                IndexName='document_index',
                KeyConditionExpression='document_id = :document_id',
            )
            docs = response.get("Items")
            if not docs:
                raise KeyError(f"Document not found for document_id {document_id}")
            if len(docs) > 1:
                raise ValueError(f"Multiple items found for document_id {document_id}")

            logging.info(docs[0])

            return docs[0]
        except ClientError as e:
            print(f"Error querying document: {e.response['Error']['Message']}")
            raise

    def _get_documents_by_name(self, repository_id: str, collection_id: str, document_name: str) -> list[RagDocument]:
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
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq(pk),
            FilterExpression=Key("document_name").eq(document_name)
        )
        docs: list[RagDocument] = response["Items"]

        # Handle paginated Dynamo results
        while "LastEvaluatedKey" in response:
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(pk),
                FilterExpression=Key("document_name").eq(document_name),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            docs.extend(response["Items"])

        return docs

    def list_all(self, repository_id: str, collection_id: str)-> List[RagDocument]:
        """List all documents in a collection.

        Args:
            repository_id: Repository ID
            collection_id: Collection ID

        Returns:
            List of documents
        """
        pk = RagDocument.createPartitionKey(repository_id, collection_id)
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq(pk),
        )
        docs: list[RagDocument] = response["Items"]

        # Handle paginated Dynamo results
        while "LastEvaluatedKey" in response:
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(pk),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            docs.extend(response["Items"])

        return docs
