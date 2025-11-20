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

"""PGVector repository service implementation."""

import json
import logging
import os

import boto3
from langchain_community.vectorstores import PGVector
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from repository.embeddings import RagEmbeddings
from utilities.common_functions import get_lambda_role_name, retry_config
from utilities.rds_auth import generate_auth_token
from utilities.repository_types import RepositoryType

from .vector_store_repository_service import VectorStoreRepositoryService

logger = logging.getLogger(__name__)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
secretsmanager_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)


class PGVectorRepositoryService(VectorStoreRepositoryService):
    """Service for PGVector repository operations.

    Inherits common vector store behavior from VectorStoreRepositoryService.
    Only implements PGVector-specific collection management and score normalization.
    """

    def _drop_collection_index(self, collection_id: str) -> None:
        """Drop PGVector collection table."""
        try:
            logger.info(f"Dropping PGVector collection for {collection_id}")

            embeddings = RagEmbeddings(model_name=collection_id)
            vector_store = self._get_vector_store_client(
                collection_id=collection_id,
                embeddings=embeddings,
            )

            # Drop the collection if supported
            if hasattr(vector_store, "delete_collection"):
                vector_store.delete_collection()
                logger.info(f"Dropped PGVector collection: {collection_id}")
            else:
                logger.warning("Vector store does not support collection deletion")

        except Exception as e:
            logger.error(f"Failed to drop PGVector collection: {e}", exc_info=True)
            # Don't raise - continue with document deletion

    def _normalize_similarity_score(self, score: float) -> float:
        """Convert PGVector cosine distance to similarity score.

        PGVector returns cosine distance (0-2 range, lower = more similar).
        Convert to similarity (0-1 range, higher = more similar).

        Args:
            score: Cosine distance from PGVector

        Returns:
            Similarity score in 0-1 range
        """
        return max(0.0, 1.0 - (score / 2.0))

    def _get_vector_store_client(self, collection_id: str, embeddings: Embeddings) -> VectorStore:
        """Get PGVector vector store client.

        Args:
            collection_id: Collection identifier
            embeddings: Embeddings adapter

        Returns:
            PGVector client instance
        """
        prefix = os.environ.get("REGISTERED_REPOSITORIES_PS_PREFIX")
        connection_info = ssm_client.get_parameter(Name=f"{prefix}{self.repository_id}")
        connection_info = json.loads(connection_info["Parameter"]["Value"])

        if not RepositoryType.is_type(connection_info, RepositoryType.PGVECTOR):
            raise ValueError(f"Repository {self.repository_id} is not a PGVector repository")

        if "passwordSecretId" in connection_info:
            # Provides backwards compatibility to non-IAM authenticated vector stores
            secrets_response = secretsmanager_client.get_secret_value(SecretId=connection_info.get("passwordSecretId"))
            user = connection_info.get("username")
            password = json.loads(secrets_response.get("SecretString")).get("password")
        else:
            # Use IAM auth token to connect
            user = get_lambda_role_name()
            password = generate_auth_token(connection_info.get("dbHost"), connection_info.get("dbPort"), user)

        connection_string = PGVector.connection_string_from_db_params(
            driver="psycopg2",
            host=connection_info.get("dbHost"),
            port=connection_info.get("dbPort"),
            database=connection_info.get("dbName"),
            user=user,
            password=password,
        )

        return PGVector(
            collection_name=collection_id,
            connection_string=connection_string,
            embedding_function=embeddings,
        )
