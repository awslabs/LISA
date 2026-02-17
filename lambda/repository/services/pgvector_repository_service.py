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
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_postgres import PGEngine, PGVectorStore
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
            if hasattr(vector_store, "drop_tables"):
                vector_store.drop_tables()
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
        return min(1.0, max(0.0, 1.0 - (score / 2.0)))

    def _create_engine(self) -> PGEngine:
        """Create a PGEngine instance from repository connection configuration.

        Returns:
            PGEngine connected to the repository's database

        Raises:
            ValueError: If repository is not registered or not a PGVector repository
        """
        prefix = os.environ.get("REGISTERED_REPOSITORIES_PS_PREFIX")
        parameter_name = f"{prefix}{self.repository_id}"

        try:
            connection_info = ssm_client.get_parameter(Name=parameter_name)
            connection_info = json.loads(connection_info["Parameter"]["Value"])
        except ssm_client.exceptions.ParameterNotFound:
            logger.error(
                f"Repository '{self.repository_id}' not found in SSM Parameter Store. "
                f"Parameter: {parameter_name}. "
                f"Ensure the repository is registered before use."
            )
            raise ValueError(
                f"Repository '{self.repository_id}' is not registered. "
                f"Please register the repository before performing operations."
            )

        if not RepositoryType.is_type(connection_info, RepositoryType.PGVECTOR):
            raise ValueError(f"Repository {self.repository_id} is not a PGVector repository")

        # Check if using password auth (passwordSecretId present) or IAM auth
        if "passwordSecretId" in connection_info:
            secrets_response = secretsmanager_client.get_secret_value(SecretId=connection_info.get("passwordSecretId"))
            user = connection_info.get("username")
            password = json.loads(secrets_response.get("SecretString")).get("password")
            ssl_mode = None
        else:
            user = get_lambda_role_name()
            password = generate_auth_token(connection_info.get("dbHost"), connection_info.get("dbPort"), user)
            ssl_mode = "require"

        host = connection_info.get("dbHost")
        port = int(connection_info.get("dbPort"))
        database = connection_info.get("dbName")

        connection_string = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
        if ssl_mode:
            connection_string = f"{connection_string}?sslmode={ssl_mode}"

        return PGEngine.from_connection_string(url=connection_string)

    def initialize_collection(self, collection_id: str, embedding_model: str) -> None:
        """Create the PGVector table for a new collection.

        Args:
            collection_id: Collection identifier (used as the table name)
            embedding_model: Embedding model name for determining vector dimensions
        """
        embeddings = RagEmbeddings(model_name=embedding_model)
        engine = self._create_engine()
        sample_embedding = embeddings.embed_query("dimension probe")
        vector_size = len(sample_embedding)
        engine.init_vectorstore_table(
            table_name=collection_id,
            vector_size=vector_size,
        )
        logger.info(f"Initialized PGVector table for collection '{collection_id}' with vector_size={vector_size}")

    def _get_vector_store_client(self, collection_id: str, embeddings: Embeddings) -> VectorStore:
        """Get PGVector vector store client.

        Assumes the collection table already exists (created by initialize_collection).

        Args:
            collection_id: Collection identifier
            embeddings: Embeddings adapter

        Returns:
            PGVectorStore client instance
        """
        engine = self._create_engine()

        return PGVectorStore.create_sync(
            engine=engine,
            table_name=collection_id,
            embedding_service=embeddings,
        )


