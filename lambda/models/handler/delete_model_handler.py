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

"""Handler for DeleteModel requests."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from models.exception import ModelInUseError, ModelNotFoundError
from repository.collection_repo import CollectionRepository
from repository.vector_store_repo import VectorStoreRepository

from ..domain_objects import DeleteModelResponse
from .base_handler import BaseApiHandler
from .utils import to_lisa_model

logger = logging.getLogger(__name__)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])


class DeleteModelHandler(BaseApiHandler):
    """Handler class for DeleteModel requests."""

    def __call__(self, model_id: str) -> DeleteModelResponse:
        """Kick off state machine to delete infrastructure and remove model reference from LiteLLM."""
        table_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if not table_item:
            raise ModelNotFoundError(f"Model '{model_id}' was not found")

        # Check if model is associated with any pipelines (embedding models only)
        self._check_model_in_use(model_id)

        self._stepfunctions.start_execution(
            stateMachineArn=os.environ["DELETE_SFN_ARN"], input=json.dumps({"modelId": model_id})
        )

        lisa_model = to_lisa_model(table_item)
        return DeleteModelResponse(model=lisa_model)

    def _check_model_in_use(self, model_id: str) -> None:
        """Check if model is in use by any repository, collection, or pipeline.

        Args:
            model_id: The model ID to check

        Raises:
            ModelInUseError: If model is in use by any repository, collection, or pipeline
        """
        # Try to get vector store table name from SSM parameter (only exists if RAG is deployed)
        vector_store_table = self._get_vector_store_table_name()
        if not vector_store_table:
            logger.info(f"RAG vector store not deployed, skipping model usage check for '{model_id}'")
            return

        all_usages = []

        # Check repositories and pipelines
        vector_store_repo = VectorStoreRepository(table_name=vector_store_table)
        repo_usages = vector_store_repo.find_repositories_using_model(model_id)
        all_usages.extend([f"repository '{usage['repository_id']}' ({usage['usage_type']})" for usage in repo_usages])

        # Check collections
        collection_table = self._get_collection_table_name()
        if collection_table:
            collection_repo = CollectionRepository(table_name=collection_table)
            collection_usages = collection_repo.find_collections_using_model(model_id)
            all_usages.extend(
                [
                    f"collection '{usage['collection_id']}' in repository '{usage['repository_id']}'"
                    for usage in collection_usages
                ]
            )

        if all_usages:
            usage_list = ", ".join(all_usages)
            logger.warning(f"Model '{model_id}' is in use by: {usage_list}. Cannot delete.")
            raise ModelInUseError(
                f"Model '{model_id}' is currently in use by: {usage_list}. "
                "Please remove the model from all resources before deleting."
            )

    def _get_vector_store_table_name(self) -> str | None:
        """Get the RAG vector store table name from SSM parameter.

        Returns:
            Table name if RAG is deployed, None otherwise
        """
        parameter_name = os.environ.get("LISA_RAG_VECTOR_STORE_TABLE_PS_NAME")
        if not parameter_name:
            logger.debug("LISA_RAG_VECTOR_STORE_TABLE_PS_NAME not configured")
            return None

        try:
            response = ssm_client.get_parameter(Name=parameter_name)
            table_name = response["Parameter"]["Value"]
            logger.debug(f"Retrieved RAG vector store table name from SSM: {table_name}")
            return table_name
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.debug(f"SSM parameter {parameter_name} not found - RAG not deployed")
                return None
            logger.warning(f"Error retrieving SSM parameter {parameter_name}: {e}")
            return None

    def _get_collection_table_name(self) -> str | None:
        """Get the RAG collections table name from SSM parameter.

        Returns:
            Table name if RAG is deployed, None otherwise
        """
        parameter_name = os.environ.get("LISA_RAG_COLLECTIONS_TABLE_PS_NAME")
        if not parameter_name:
            logger.debug("LISA_RAG_COLLECTIONS_TABLE_PS_NAME not configured")
            return None

        try:
            response = ssm_client.get_parameter(Name=parameter_name)
            table_name = response["Parameter"]["Value"]
            logger.debug(f"Retrieved RAG collections table name from SSM: {table_name}")
            return table_name
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.debug(f"SSM parameter {parameter_name} not found - RAG not deployed")
                return None
            logger.warning(f"Error retrieving SSM parameter {parameter_name}: {e}")
            return None
