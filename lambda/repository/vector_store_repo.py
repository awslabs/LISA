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
import time
from typing import Any, cast, List

import boto3
from boto3.dynamodb.conditions import Attr
from models.domain_objects import VectorStoreStatus
from utilities.common_functions import retry_config
from utilities.encoders import convert_decimal

logger = logging.getLogger(__name__)


class VectorStoreRepository:
    """Vector Store repository for DynamoDB"""

    def __init__(self, table_name: str | None = None) -> None:
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        if table_name is None:
            table_name = os.environ["LISA_RAG_VECTOR_STORE_TABLE"]
        self.table = dynamodb.Table(table_name)

    def get_registered_repositories(self) -> List[dict]:
        """Get a list of all registered RAG repositories with default values for new fields."""
        response = self.table.scan()
        items = response["Items"]
        while "LastEvaluatedKey" in response:
            response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response["Items"])
        # Convert all ddb Numbers to floats to correctly serialize to json
        items = convert_decimal(items)

        registered_repositories = []
        for item in items:
            config = item.get("config", {})
            config["status"] = item.get("status", VectorStoreStatus.UNKNOWN)
            if item.get("legacy", False):
                config["legacy"] = True

            if "metadata" not in config:
                config["metadata"] = {"tags": []}
            elif isinstance(config["metadata"], dict) and "tags" not in config["metadata"]:
                config["metadata"]["tags"] = []

            registered_repositories.append(config)

        return registered_repositories

    def get_repository_status(self) -> dict[str, str]:
        """Get a list the status of all repositories"""
        status: dict[str, str] = {}

        response = self.table.scan(
            ProjectionExpression="repositoryId, #status", ExpressionAttributeNames={"#status": "status"}
        )
        items = response["Items"]
        while "LastEvaluatedKey" in response:
            response = self.table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ProjectionExpression="repositoryId, #status",
                ExpressionAttributeNames={"#status": "status"},
            )
            items.extend(response["Items"])

        status = {item["repositoryId"]: item["status"] for item in items}
        return status

    def find_repository_by_id(self, repository_id: str, raw_config: bool = False) -> dict[str, Any]:
        """
        Find a repository by its ID.

        Args:
            repository_id: The ID of the repository to find.
            raw_config: return the full object in dynamo, instead of just the repository config portion
        Returns:
            The repository configuration with default values for new fields.

        Raises:
            ValueError: If the repository is not found or the table does not exist.
        """
        try:
            response = self.table.get_item(
                Key={"repositoryId": repository_id},
            )
        except Exception as e:
            raise ValueError(f"Failed to update repository: {repository_id}", e)

        if "Item" not in response:
            raise ValueError(f"Repository with ID '{repository_id}' not found")

        repository: dict[str, Any] = convert_decimal(response.get("Item"))

        if raw_config:
            return repository

        # Get config and apply defaults for backward compatibility
        config = cast(dict[str, Any], repository.get("config", {}))
        config["status"] = repository.get("status")

        if "metadata" not in config:
            config["metadata"] = {"tags": []}
        elif isinstance(config["metadata"], dict) and "tags" not in config["metadata"]:
            config["metadata"]["tags"] = []

        return config

    def update(self, repository_id: str, updates: dict[str, Any], status: str | None = None) -> dict[str, Any]:
        """
        Update a repository configuration.

        Args:
            repository_id: The ID of the repository to update.
            updates: Dictionary of fields to update in the config.
            status: Optional status to set (if None, status is not updated).

        Returns:
            The updated repository configuration.

        Raises:
            ValueError: If the update fails or repository not found.
        """
        try:
            current = self.table.get_item(Key={"repositoryId": repository_id})
            if "Item" not in current:
                raise ValueError(f"Repository with ID '{repository_id}' not found")

            # Keep original config with Decimal types intact
            config: dict[str, Any] = current["Item"].get("config", {})
            config.update(updates)

            update_expr = "SET #config = :config, #updatedAt = :updatedAt"
            expr_names = {"#config": "config", "#updatedAt": "updatedAt"}
            expr_values = {":config": config, ":updatedAt": int(time.time() * 1000)}

            if status is not None:
                update_expr += ", #status = :status"
                expr_names["#status"] = "status"
                expr_values[":status"] = status

            self.table.update_item(
                Key={"repositoryId": repository_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )

            return config
        except Exception as e:
            raise ValueError(f"Failed to update repository: {repository_id}", e)

    def delete(self, repository_id: str) -> bool:
        """
        Delete a repository by its ID.

        Args:
            repository_id: The ID of the repository to delete.

        Returns:
            True if deletion was successful.

        Raises:
            ValueError: If the deletion fails.
        """
        try:
            self.table.delete_item(Key={"repositoryId": repository_id})
            return True
        except Exception as e:
            raise ValueError(f"Failed to delete repository: {repository_id}", e)

    def find_repositories_using_model(self, model_id: str) -> List[dict]:
        """
        Find all repositories that use a specific model.
        Excludes repositories with status indicating they are deleted or archived.

        Args:
            model_id: The model ID to search for

        Returns:
            List of dictionaries containing repository_id and usage_type
        """
        # Define statuses that are considered "active" repositories
        # Based on vector_store_repository_service.py logic
        active_statuses = {
            VectorStoreStatus.CREATE_COMPLETE,
            VectorStoreStatus.UPDATE_COMPLETE,
            VectorStoreStatus.UPDATE_COMPLETE_CLEANUP_IN_PROGRESS,
            VectorStoreStatus.UPDATE_IN_PROGRESS,
        }

        # Filter for repositories that have the model at the repository level
        # Include status in projection to filter out inactive repositories
        response = self.table.scan(
            FilterExpression=Attr("config.embeddingModelId").eq(model_id),
            ProjectionExpression="repositoryId, config.repositoryId, config.embeddingModelId, #status",
            ExpressionAttributeNames={"#status": "status"},
        )
        repositories = response["Items"]

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = self.table.scan(
                FilterExpression=Attr("config.embeddingModelId").eq(model_id),
                ProjectionExpression="repositoryId, config.repositoryId, config.embeddingModelId, #status",
                ExpressionAttributeNames={"#status": "status"},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            repositories.extend(response["Items"])

        # Process repositories with matching embeddingModelId, excluding inactive ones
        usages = []
        for repo in repositories:
            config = repo.get("config", {})
            repository_id = config.get("repositoryId", repo.get("repositoryId", "unknown"))
            status = repo.get("status", VectorStoreStatus.UNKNOWN)

            # Only include repositories with active statuses
            if status not in active_statuses:
                logger.debug(f"Skipping repository {repository_id} with inactive status {status}")
                continue

            usages.append({"repository_id": repository_id, "usage_type": "repository"})

        logger.info(f"Found {len(usages)} active repositories using model {model_id}")
        return usages
