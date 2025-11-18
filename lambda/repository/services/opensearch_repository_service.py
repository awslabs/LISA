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

"""OpenSearch repository service implementation."""

import logging

from repository.embeddings import RagEmbeddings
from utilities.vector_store import get_vector_store_client

from .vector_store_repository_service import VectorStoreRepositoryService

logger = logging.getLogger(__name__)


class OpenSearchRepositoryService(VectorStoreRepositoryService):
    """Service for OpenSearch repository operations.
    
    Inherits common vector store behavior from VectorStoreRepositoryService.
    Only implements OpenSearch-specific index management.
    """

    def _drop_collection_index(self, collection_id: str) -> None:
        """Drop OpenSearch index for collection."""
        try:
            logger.info(f"Dropping OpenSearch index for collection {collection_id}")
            
            embeddings = RagEmbeddings(model_name=collection_id)
            vector_store = get_vector_store_client(
                self.repository_id,
                collection_id=collection_id,
                embeddings=embeddings,
            )
            
            # Drop the index if it exists
            if hasattr(vector_store, "client") and hasattr(vector_store.client, "indices"):
                index_name = f"{self.repository_id}_{collection_id}".lower()
                if vector_store.client.indices.exists(index=index_name):
                    vector_store.client.indices.delete(index=index_name)
                    logger.info(f"Dropped OpenSearch index: {index_name}")
                else:
                    logger.info(f"OpenSearch index {index_name} does not exist")
            else:
                logger.warning("Vector store client does not support index operations")
                
        except Exception as e:
            logger.error(f"Failed to drop OpenSearch index: {e}", exc_info=True)
            # Don't raise - continue with document deletion

    # OpenSearch uses default score normalization (0-1 range already)
