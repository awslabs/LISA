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

import logging

from repository.embeddings import RagEmbeddings
from utilities.vector_store import get_vector_store_client

from .vector_store_repository_service import VectorStoreRepositoryService

logger = logging.getLogger(__name__)


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
            vector_store = get_vector_store_client(
                self.repository_id,
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
