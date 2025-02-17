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
from typing import Any, cast, List

import boto3
from utilities.common_functions import retry_config
from utilities.encoders import convert_decimal

logger = logging.getLogger(__name__)


class VectorStoreRepository:
    """Vector Store repository for DynamoDB"""

    def __init__(self) -> None:
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        self.table = dynamodb.Table(os.environ["LISA_RAG_VECTOR_STORE_TABLE"])

    def get_registered_repositories(self) -> List[dict]:
        """Get a list of all registered RAG repositories."""
        response = self.table.scan()
        items = response["Items"]
        while "LastEvaluatedKey" in response:
            response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response["Items"])
        # Convert all ddb Numbers to floats to correctly serialize to json
        items = convert_decimal(items)

        registered_repositories = []
        for item in items:
            item["config"]["legacy"] = item.get("legacy", False)
            registered_repositories.append(item["config"])

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
            The repository configuration.

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
        return repository if raw_config else cast(dict[str, Any], repository.get("config", {}))

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
