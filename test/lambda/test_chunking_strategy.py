#!/usr/bin/env python3
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

"""Unit tests for chunking strategy implementations."""

import json
import sys
import unittest
from unittest.mock import MagicMock

from langchain_core.documents import Document
from models.domain_objects import ChunkingStrategyType, FixedChunkingStrategy, NoneChunkingStrategy
from utilities.chunking_strategy_factory import ChunkingStrategyFactory, FixedSizeChunkingHandler, NoneChunkingHandler

# Add parent directory to path for imports
sys.path.insert(0, "..")


class TestChunkingStrategySchemas(unittest.TestCase):
    """Test chunking strategy schema validation and serialization."""

    def test_none_strategy_creation(self):
        """Test NONE strategy can be created with correct type."""
        strategy = NoneChunkingStrategy()
        self.assertEqual(strategy.type, ChunkingStrategyType.NONE)

    def test_none_strategy_serialization(self):
        """Test NONE strategy serializes to correct JSON."""
        strategy = NoneChunkingStrategy()
        serialized = strategy.model_dump()

        self.assertIn("type", serialized)
        self.assertEqual(serialized["type"], ChunkingStrategyType.NONE)

        # Verify JSON serialization
        json_str = json.dumps(serialized, default=str)
        self.assertIn('"type"', json_str)
        self.assertIn("none", json_str.lower())

    def test_fixed_strategy_still_works(self):
        """Test FIXED strategy continues to work correctly."""
        strategy = FixedChunkingStrategy(size=512, overlap=51)

        self.assertEqual(strategy.type, ChunkingStrategyType.FIXED)
        self.assertEqual(strategy.size, 512)
        self.assertEqual(strategy.overlap, 51)

    def test_fixed_strategy_validation(self):
        """Test FIXED strategy validates overlap correctly."""
        # Valid overlap (less than half of size)
        strategy = FixedChunkingStrategy(size=512, overlap=51)
        self.assertEqual(strategy.overlap, 51)

        # Invalid overlap (more than half of size) should raise error
        with self.assertRaises(ValueError) as context:
            FixedChunkingStrategy(size=512, overlap=300)

        self.assertIn("overlap", str(context.exception).lower())

    def test_invalid_strategy_type_rejected(self):
        """Test that invalid strategy types are rejected."""
        # This test verifies enum validation
        with self.assertRaises((ValueError, AttributeError)):
            # Try to create with invalid type
            ChunkingStrategyType("invalid_type")


class TestNoneChunkingHandler(unittest.TestCase):
    """Test NoneChunkingHandler implementation."""

    def test_handler_returns_documents_unmodified(self):
        """Test NONE handler returns documents without modification."""
        handler = NoneChunkingHandler()
        strategy = NoneChunkingStrategy()

        # Create test documents
        docs = [
            Document(page_content="Document 1", metadata={"source": "test1"}),
            Document(page_content="Document 2", metadata={"source": "test2"}),
            Document(page_content="Document 3", metadata={"source": "test3"}),
        ]

        # Process documents
        result = handler.chunk_documents(docs, strategy)

        # Verify documents are returned unmodified
        self.assertEqual(len(result), 3)
        self.assertEqual(result, docs)
        self.assertEqual(result[0].page_content, "Document 1")
        self.assertEqual(result[1].page_content, "Document 2")
        self.assertEqual(result[2].page_content, "Document 3")

    def test_handler_preserves_metadata(self):
        """Test NONE handler preserves document metadata."""
        handler = NoneChunkingHandler()
        strategy = NoneChunkingStrategy()

        # Create document with metadata
        docs = [
            Document(page_content="Test content", metadata={"source": "test.txt", "author": "Test Author", "page": 1})
        ]

        result = handler.chunk_documents(docs, strategy)

        self.assertEqual(result[0].metadata["source"], "test.txt")
        self.assertEqual(result[0].metadata["author"], "Test Author")
        self.assertEqual(result[0].metadata["page"], 1)

    def test_handler_with_empty_list(self):
        """Test NONE handler handles empty document list."""
        handler = NoneChunkingHandler()
        strategy = NoneChunkingStrategy()

        result = handler.chunk_documents([], strategy)

        self.assertEqual(len(result), 0)
        self.assertEqual(result, [])


class TestChunkingStrategyFactory(unittest.TestCase):
    """Test ChunkingStrategyFactory registration and routing."""

    def test_none_handler_registered(self):
        """Test NONE handler is registered in factory."""
        self.assertIn(ChunkingStrategyType.NONE, ChunkingStrategyFactory._handlers)

        handler = ChunkingStrategyFactory._handlers[ChunkingStrategyType.NONE]
        self.assertIsInstance(handler, NoneChunkingHandler)

    def test_fixed_handler_still_registered(self):
        """Test FIXED handler remains registered."""
        self.assertIn(ChunkingStrategyType.FIXED, ChunkingStrategyFactory._handlers)

        handler = ChunkingStrategyFactory._handlers[ChunkingStrategyType.FIXED]
        self.assertIsInstance(handler, FixedSizeChunkingHandler)

    def test_factory_routes_none_strategy(self):
        """Test factory routes NONE strategy to correct handler."""
        strategy = NoneChunkingStrategy()
        docs = [Document(page_content="Test")]

        result = ChunkingStrategyFactory.chunk_documents(docs, strategy)

        # Should return documents unmodified
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].page_content, "Test")

    def test_factory_routes_fixed_strategy(self):
        """Test factory routes FIXED strategy to correct handler."""
        strategy = FixedChunkingStrategy(size=100, overlap=10)
        docs = [Document(page_content="A" * 500)]  # Long document

        result = ChunkingStrategyFactory.chunk_documents(docs, strategy)

        # Should chunk the document
        self.assertGreater(len(result), 1)

    def test_get_supported_strategies(self):
        """Test factory returns all supported strategies."""
        strategies = ChunkingStrategyFactory.get_supported_strategies()

        self.assertIn(ChunkingStrategyType.FIXED, strategies)
        self.assertIn(ChunkingStrategyType.NONE, strategies)
        self.assertEqual(len(strategies), 2)

    def test_unsupported_strategy_raises_error(self):
        """Test factory raises error for unsupported strategy type."""
        # Create a mock strategy with invalid type
        mock_strategy = MagicMock()
        mock_strategy.type = "invalid_type"

        with self.assertRaises(ValueError) as context:
            ChunkingStrategyFactory.chunk_documents([], mock_strategy)

        self.assertIn("Unsupported chunking strategy", str(context.exception))


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility with existing FIXED strategy."""

    def test_default_strategy_is_fixed(self):
        """Test default strategy remains FIXED."""
        from utilities.chunking_strategy_factory import DEFAULT_STRATEGY

        self.assertEqual(DEFAULT_STRATEGY.type, ChunkingStrategyType.FIXED)
        self.assertEqual(DEFAULT_STRATEGY.size, 512)
        self.assertEqual(DEFAULT_STRATEGY.overlap, 51)

    def test_none_parameter_uses_default(self):
        """Test passing None uses default FIXED strategy."""
        docs = [Document(page_content="A" * 1000)]

        result = ChunkingStrategyFactory.chunk_documents(docs, None)

        # Should chunk using default FIXED strategy
        self.assertGreater(len(result), 1)


if __name__ == "__main__":
    unittest.main()
