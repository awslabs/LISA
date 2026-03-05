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

"""Collection repository for DynamoDB operations."""

import logging
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from models.domain_objects import CollectionSortBy, CollectionStatus, RagCollectionConfig, SortOrder
from utilities.common_functions import retry_config
from utilities.encoders import convert_decimal
from utilities.time import iso_string, utc_now

logger = logging.getLogger(__name__)


class CollectionRepositoryError(Exception):
    """Exception raised for errors in collection repository operations."""

    pass


class CollectionRepository:
    """Collection repository for DynamoDB operations."""

    def __init__(self, table_name: str | None = None) -> None:
        """
        Initialize the Collection Repository.

        Args:
            table_name: Optional table name override for testing
        """
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        table_name = table_name or os.environ.get("LISA_RAG_COLLECTIONS_TABLE", "LisaRagCollectionsTable")
        self.table = dynamodb.Table(table_name)
        logger.info(f"Initialized CollectionRepository with table: {table_name}")

    def create(self, collection: RagCollectionConfig) -> RagCollectionConfig:
        """
        Create a new collection in DynamoDB.

        Args:
            collection: The collection configuration to create

        Returns:
            The created collection configuration

        Raises:
            CollectionRepositoryError: If creation fails
        """
        try:
            # Ensure timestamps are set
            now = utc_now()
            if not collection.createdAt:
                collection.createdAt = now
            if not collection.updatedAt:
                collection.updatedAt = now

            # Convert to dict for DynamoDB
            item = collection.model_dump()

            # Convert datetime objects to ISO strings
            item["createdAt"] = collection.createdAt.isoformat()
            item["updatedAt"] = collection.updatedAt.isoformat()

            # Put item with condition to prevent overwriting
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(collectionId)",
            )

            logger.info(f"Created collection: {collection.collectionId}")
            return collection

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise CollectionRepositoryError(f"Collection with ID '{collection.collectionId}' already exists")
            logger.error(f"Failed to create collection: {e}")
            raise CollectionRepositoryError(f"Failed to create collection: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating collection: {e}")
            raise CollectionRepositoryError(f"Unexpected error creating collection: {str(e)}")

    def find_by_id(self, collection_id: str, repository_id: str) -> RagCollectionConfig | None:
        """
        Find a collection by its ID and repository ID.

        Args:
            collection_id: The collection ID
            repository_id: The repository ID

        Returns:
            The collection configuration if found, None otherwise

        Raises:
            CollectionRepositoryError: If retrieval fails
        """
        try:
            response = self.table.get_item(
                Key={
                    "collectionId": collection_id,
                    "repositoryId": repository_id,
                },
                ConsistentRead=True,
            )

            if "Item" not in response:
                return None

            item = convert_decimal(response["Item"])
            return RagCollectionConfig(**item)

        except Exception as e:
            logger.error(f"Failed to find collection {collection_id}: {e}")
            raise CollectionRepositoryError(f"Failed to find collection: {str(e)}")

    def update(
        self,
        collection_id: str,
        repository_id: str,
        updates: dict[str, Any],
        expected_version: str | None = None,
    ) -> RagCollectionConfig:
        """
        Update a collection with optimistic locking.

        Args:
            collection_id: The collection ID
            repository_id: The repository ID
            updates: Dictionary of fields to update
            expected_version: Expected updatedAt timestamp for optimistic locking

        Returns:
            The updated collection configuration

        Raises:
            CollectionRepositoryError: If update fails
        """
        try:
            # Build update expression
            update_expr_parts = []
            expr_attr_names = {}
            expr_attr_values = {}

            # Always update the updatedAt timestamp
            updates["updatedAt"] = iso_string()

            for key, value in updates.items():
                # Skip immutable fields
                if key in ["collectionId", "repositoryId", "createdBy", "createdAt", "embeddingModel"]:
                    logger.warning(f"Skipping immutable field: {key}")
                    continue

                # Use attribute names to handle reserved words
                attr_name = f"#{key}"
                attr_value = f":{key}"
                update_expr_parts.append(f"{attr_name} = {attr_value}")
                expr_attr_names[attr_name] = key
                expr_attr_values[attr_value] = value

            if not update_expr_parts:
                raise CollectionRepositoryError("No valid fields to update")

            update_expression = "SET " + ", ".join(update_expr_parts)

            # Build condition expression for optimistic locking
            condition_expression = "attribute_exists(collectionId)"
            if expected_version:
                condition_expression += " AND updatedAt = :expected_version"
                expr_attr_values[":expected_version"] = expected_version

            # Perform update
            response = self.table.update_item(
                Key={
                    "collectionId": collection_id,
                    "repositoryId": repository_id,
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
                ConditionExpression=condition_expression,
                ReturnValues="ALL_NEW",
            )

            item = convert_decimal(response["Attributes"])
            logger.info(f"Updated collection: {collection_id}")
            return RagCollectionConfig(**item)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                if expected_version:
                    raise CollectionRepositoryError("Collection was modified by another process. Please retry.")
                raise CollectionRepositoryError(f"Collection '{collection_id}' not found")
            logger.error(f"Failed to update collection {collection_id}: {e}")
            raise CollectionRepositoryError(f"Failed to update collection: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error updating collection {collection_id}: {e}")
            raise CollectionRepositoryError(f"Unexpected error updating collection: {str(e)}")

    def delete(self, collection_id: str, repository_id: str) -> bool:
        """
        Delete a collection from DynamoDB.

        Args:
            collection_id: The collection ID
            repository_id: The repository ID

        Returns:
            True if deletion was successful

        Raises:
            CollectionRepositoryError: If deletion fails
        """
        try:
            self.table.delete_item(
                Key={
                    "collectionId": collection_id,
                    "repositoryId": repository_id,
                },
                ConditionExpression="attribute_exists(collectionId)",
            )
            logger.info(f"Deleted collection: {collection_id}")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise CollectionRepositoryError(f"Collection '{collection_id}' not found")
            logger.error(f"Failed to delete collection {collection_id}: {e}")
            raise CollectionRepositoryError(f"Failed to delete collection: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error deleting collection {collection_id}: {e}")
            raise CollectionRepositoryError(f"Unexpected error deleting collection: {str(e)}")

    def list_by_repository(
        self,
        repository_id: str,
        page_size: int = 20,
        last_evaluated_key: dict[str, str] | None = None,
        filter_text: str | None = None,
        status_filter: CollectionStatus | None = None,
        sort_by: CollectionSortBy = CollectionSortBy.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> tuple[list[RagCollectionConfig], dict[str, str] | None]:
        """
        List collections for a repository with pagination, filtering, and sorting.

        Args:
            repository_id: The repository ID
            page_size: Number of items per page (max 100)
            last_evaluated_key: Pagination token from previous request
            filter_text: Optional text to filter by name or description
            status_filter: Optional status to filter by
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)

        Returns:
            Tuple of (list of collections, last_evaluated_key for pagination)

        Raises:
            CollectionRepositoryError: If listing fails
        """
        try:
            # Limit page size to 100
            page_size = min(page_size, 100)

            # Determine which index to use based on filters
            if status_filter:
                index_name = "StatusIndex"
                key_condition = Key("repositoryId").eq(repository_id) & Key("status").eq(status_filter.value)
            else:
                index_name = "RepositoryIndex"
                key_condition = Key("repositoryId").eq(repository_id)

            # Build query parameters
            query_params = {
                "IndexName": index_name,
                "KeyConditionExpression": key_condition,
                "Limit": page_size,
                "ScanIndexForward": (sort_order == SortOrder.ASC),
            }

            if last_evaluated_key:
                query_params["ExclusiveStartKey"] = last_evaluated_key

            # Execute query
            response = self.table.query(**query_params)

            # Convert items to collection objects
            items = [convert_decimal(item) for item in response.get("Items", [])]
            collections = [RagCollectionConfig(**item) for item in items]

            # Apply text filter if provided (post-query filtering)
            if filter_text:
                filter_text_lower = filter_text.lower()
                collections = [
                    c
                    for c in collections
                    if (c.name and filter_text_lower in c.name.lower())
                    or (c.description and filter_text_lower in c.description.lower())
                ]

            # Sort collections if needed (for non-default sort fields)
            if sort_by != CollectionSortBy.CREATED_AT:
                reverse = sort_order == SortOrder.DESC
                if sort_by == CollectionSortBy.NAME:
                    collections.sort(key=lambda c: c.name or "", reverse=reverse)
                elif sort_by == CollectionSortBy.UPDATED_AT:
                    collections.sort(key=lambda c: c.updatedAt, reverse=reverse)

            # Get pagination token
            next_key = response.get("LastEvaluatedKey")

            logger.info(f"Listed {len(collections)} collections for repository {repository_id}")
            return collections, next_key

        except Exception as e:
            logger.error(f"Failed to list collections for repository {repository_id}: {e}")
            raise CollectionRepositoryError(f"Failed to list collections: {str(e)}")

    def count_by_repository(self, repository_id: str, status: CollectionStatus | None = None) -> int:
        """
        Count collections in a repository.

        Args:
            repository_id: The repository ID
            status: Optional status filter

        Returns:
            Number of collections

        Raises:
            CollectionRepositoryError: If count fails
        """
        try:
            if status:
                index_name = "StatusIndex"
                key_condition = Key("repositoryId").eq(repository_id) & Key("status").eq(status.value)
            else:
                index_name = "RepositoryIndex"
                key_condition = Key("repositoryId").eq(repository_id)

            response = self.table.query(
                IndexName=index_name,
                KeyConditionExpression=key_condition,
                Select="COUNT",
            )

            count = response.get("Count", 0)
            logger.info(f"Counted {count} collections for repository {repository_id}")
            return count  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Failed to count collections for repository {repository_id}: {e}")
            raise CollectionRepositoryError(f"Failed to count collections: {str(e)}")

    def find_by_id_or_name(self, collection_id: str, repository_id: str) -> RagCollectionConfig | None:
        """Find a collection by UUID primary key, falling back to name lookup.

        Handles the case where a pipeline stores a user-entered name as collectionId.
        """
        collection = self.find_by_id(collection_id, repository_id)
        if collection:
            return collection
        return self.find_by_name(repository_id, collection_id)

    def find_by_name(self, repository_id: str, collection_name: str) -> RagCollectionConfig | None:
        try:
            query_params: dict = {
                "IndexName": "RepositoryIndex",
                "KeyConditionExpression": Key("repositoryId").eq(repository_id),
                "FilterExpression": "#name = :name",
                "ExpressionAttributeNames": {"#name": "name"},
                "ExpressionAttributeValues": {":name": collection_name},
            }
            while True:
                response = self.table.query(**query_params)
                items = response.get("Items", [])
                if items:
                    return RagCollectionConfig(**convert_decimal(items[0]))
                if "LastEvaluatedKey" not in response:
                    return None
                query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        except Exception as e:
            logger.error(f"Failed to find collection by name '{collection_name}': {e}")
            raise CollectionRepositoryError(f"Failed to find collection by name: {str(e)}")

    def find_collections_using_model(self, model_id: str) -> list[dict[str, str]]:
        """
        Find all collections that use a specific embedding model.
        Excludes collections with status indicating they are deleted or archived.

        Args:
            model_id: The model ID to search for

        Returns:
            List of dictionaries containing collection_id and repository_id
        """
        try:
            # Use FilterExpression to filter at DynamoDB level, reducing data transfer
            # Include status in projection to filter out inactive collections
            filter_expression = Attr("embeddingModel").eq(model_id)

            response = self.table.scan(
                FilterExpression=filter_expression,
                ProjectionExpression="collectionId, repositoryId, embeddingModel, #status",
                ExpressionAttributeNames={"#status": "status"},
            )
            collections = response["Items"]

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.table.scan(
                    FilterExpression=filter_expression,
                    ProjectionExpression="collectionId, repositoryId, embeddingModel, #status",
                    ExpressionAttributeNames={"#status": "status"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                collections.extend(response["Items"])

            # Convert to the expected format, filtering out inactive collections
            usages = []
            for collection in collections:
                status = collection.get("status", CollectionStatus.ACTIVE)

                # Only include active collections (exclude deleted, archived, etc.)
                if status != CollectionStatus.ACTIVE:
                    logger.debug(f"Skipping collection {collection.get('collectionId')} with status {status}")
                    continue

                usages.append(
                    {
                        "collection_id": collection.get("collectionId", "unknown"),
                        "repository_id": collection.get("repositoryId", "unknown"),
                    }
                )

            logger.info(f"Found {len(usages)} active collections using model {model_id}")
            return usages

        except Exception as e:
            logger.error(f"Failed to find collections using model {model_id}: {e}")
            raise CollectionRepositoryError(f"Failed to find collections using model: {str(e)}")
