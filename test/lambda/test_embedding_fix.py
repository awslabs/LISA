#!/usr/bin/env python3
"""
Test script to verify the embedding batch size fix works correctly.
This script tests the embedding functionality with various batch sizes.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lambda'))

from repository.embeddings import RagEmbeddings
from unittest.mock import Mock, patch
import requests


def test_batch_splitting():
    """Test that large batches are properly split into smaller chunks."""
    print("Testing batch splitting functionality...")
    
    # Create a mock embedding instance
    with patch('repository.embeddings.get_management_key', return_value='mock_token'), \
         patch('repository.embeddings.get_rest_api_container_endpoint', return_value='http://mock-api'), \
         patch('repository.embeddings.get_cert_path', return_value=False):
        
        embeddings = RagEmbeddings(model_name='test-model')
        
        # Test with a large batch (should be split)
        large_batch = [f"Test text {i}" for i in range(250)]
        
        # Mock the _embed_batch method to return fake embeddings
        def mock_embed_batch(texts):
            return [[0.1, 0.2, 0.3] for _ in texts]
        
        embeddings._embed_batch_with_retry = mock_embed_batch
        
        # This should split into multiple batches
        result = embeddings.embed_documents(large_batch)
        
        assert len(result) == 250, f"Expected 250 embeddings, got {len(result)}"
        print(f"✓ Successfully processed {len(result)} embeddings from large batch")


def test_413_error_handling():
    """Test that 413 errors are handled with batch size reduction."""
    print("Testing 413 error handling...")
    
    with patch('repository.embeddings.get_management_key', return_value='mock_token'), \
         patch('repository.embeddings.get_rest_api_container_endpoint', return_value='http://mock-api'), \
         patch('repository.embeddings.get_cert_path', return_value=False):
        
        embeddings = RagEmbeddings(model_name='test-model')
        
        # Mock requests.post to simulate 413 error on first call, success on retry
        call_count = 0
        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = Mock()
            if call_count == 1:
                # First call fails with 413
                mock_response.status_code = 413
                return mock_response
            else:
                # Subsequent calls succeed
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": [{"embedding": [0.1, 0.2, 0.3]} for _ in range(len(kwargs['json']['input']))]
                }
                return mock_response
        
        with patch('requests.post', side_effect=mock_post):
            # This should handle the 413 error and retry with smaller batch
            texts = ["Test text 1", "Test text 2"]
            result = embeddings._embed_batch_with_retry(texts)
            
            assert len(result) == 2, f"Expected 2 embeddings, got {len(result)}"
            print("✓ Successfully handled 413 error with retry mechanism")


if __name__ == "__main__":
    print("Running embedding fix tests...")
    test_batch_splitting()
    test_413_error_handling()
    print("All tests passed! ✓")