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

"""Factory pattern for creating chunking strategies."""
import logging
import os
from abc import ABC, abstractmethod
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models.domain_objects import ChunkingStrategy, ChunkingStrategyType, FixedChunkingStrategy
from utilities.exceptions import RagUploadException

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY = FixedChunkingStrategy(size=os.getenv("CHUNK_SIZE", "512"), overlap=os.getenv("CHUNK_OVERLAP", "51"))


class ChunkingStrategyHandler(ABC):
    """Abstract base class for chunking strategy handlers."""

    @abstractmethod
    def chunk_documents(self, docs: List[Document], strategy: ChunkingStrategy) -> List[Document]:
        """
        Chunk documents according to the strategy.

        Parameters
        ----------
        docs : List[Document]
            List of documents to chunk
        strategy : ChunkingStrategy
            The chunking strategy configuration

        Returns
        -------
        List[Document]
            List of chunked documents
        """
        pass


class FixedSizeChunkingHandler(ChunkingStrategyHandler):
    """Handler for fixed-size chunking strategy."""

    def chunk_documents(self, docs: List[Document], strategy: ChunkingStrategy = DEFAULT_STRATEGY) -> List[Document]:
        """
        Chunk documents using fixed-size strategy with RecursiveCharacterTextSplitter.

        Parameters
        ----------
        docs : List[Document]
            List of documents to chunk
        strategy : ChunkingStrategy
            The chunking strategy configuration (FixedChunkingStrategy)

        Returns
        -------
        List[Document]
            List of chunked documents
        """
        # Handle both legacy (size/overlap) and new (chunkSize/chunkOverlap) formats
        chunk_size = strategy.size
        chunk_overlap = strategy.overlap

        # Apply defaults from environment if not specified
        if not chunk_size:
            chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
        if not chunk_overlap:
            chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "51"))

        # Validate parameters
        if chunk_size < 100 or chunk_size > 10000:
            raise RagUploadException("Invalid chunk size: must be between 100 and 10000")

        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise RagUploadException("Invalid chunk overlap: must be non-negative and less than chunk size")

        logger.info(f"Chunking documents with fixed size strategy: size={chunk_size}, overlap={chunk_overlap}")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        return text_splitter.split_documents(docs)  # type: ignore [no-any-return]


class NoneChunkingHandler(ChunkingStrategyHandler):
    """Handler for no-chunking strategy - returns documents as-is."""

    def chunk_documents(self, docs: List[Document], strategy: ChunkingStrategy) -> List[Document]:
        """
        Return documents without chunking.

        Parameters
        ----------
        docs : List[Document]
            List of documents to process
        strategy : ChunkingStrategy
            The chunking strategy configuration (NoneChunkingStrategy)

        Returns
        -------
        List[Document]
            Original list of documents unmodified
        """
        logger.info(f"Processing {len(docs)} documents with NONE chunking strategy (no chunking)")
        return docs


class ChunkingStrategyFactory:
    """Factory for creating and executing chunking strategies."""

    _handlers = {
        ChunkingStrategyType.FIXED: FixedSizeChunkingHandler(),
        ChunkingStrategyType.NONE: NoneChunkingHandler(),
    }

    @classmethod
    def chunk_documents(cls, docs: List[Document], strategy: ChunkingStrategy = DEFAULT_STRATEGY) -> List[Document]:
        """
        Chunk documents using the appropriate strategy handler.

        Parameters
        ----------
        docs : List[Document]
            List of documents to chunk
        strategy : ChunkingStrategy
            The chunking strategy configuration

        Returns
        -------
        List[Document]
            List of chunked documents

        Raises
        ------
        ValueError
            If the chunking strategy type is not supported
        """
        if strategy is None:
            strategy = DEFAULT_STRATEGY
        handler = cls._handlers.get(strategy.type)
        if not handler:
            supported_strategies = ", ".join([s.value for s in cls._handlers.keys()])
            logger.error(
                f"Unsupported chunking strategy: {strategy.type}. Supported strategies: {supported_strategies}"
            )
            raise ValueError(f"Unsupported chunking strategy: {strategy.type}")

        return handler.chunk_documents(docs, strategy)

    @classmethod
    def register_handler(cls, strategy_type: ChunkingStrategyType, handler: ChunkingStrategyHandler) -> None:
        """
        Register a new chunking strategy handler.

        This allows for extending the factory with additional chunking strategies.

        Parameters
        ----------
        strategy_type : ChunkingStrategyType
            The strategy type to register
        handler : ChunkingStrategyHandler
            The handler instance for this strategy
        """
        cls._handlers[strategy_type] = handler
        logger.info(f"Registered chunking strategy handler: {strategy_type.value}")

    @classmethod
    def get_supported_strategies(cls) -> List[ChunkingStrategyType]:
        """
        Get list of supported chunking strategy types.

        Returns
        -------
        List[ChunkingStrategyType]
            List of supported strategy types
        """
        return list(cls._handlers.keys())
