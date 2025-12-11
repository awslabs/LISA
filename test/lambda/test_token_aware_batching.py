#!/usr/bin/env python3
"""
Test script to demonstrate token-aware batching for LiteLLM embedding limits.
Shows how the system handles MAX_BATCH_TOKENS=16384 and MAX_TOTAL_TOKENS=4096.
"""

import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def estimate_tokens(text: str) -> int:
    """More accurate token estimation for embedding models."""
    base_tokens = len(text) // 4  # Base estimate
    
    # Adjust for text characteristics
    special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text) if text else 0
    whitespace_ratio = sum(1 for c in text if c.isspace()) / len(text) if text else 0
    
    # PDF text typically has more tokens due to formatting
    if special_char_ratio > 0.1 or whitespace_ratio > 0.3:  # Likely PDF or formatted text
        adjustment_factor = 1.3  # 30% more tokens
    else:
        adjustment_factor = 1.1  # 10% more tokens for safety
    
    return int(base_tokens * adjustment_factor)

def simulate_token_aware_batching():
    """Simulate token-aware batching with different scenarios."""
    
    # Set environment variables to match your configuration
    os.environ['MAX_BATCH_TOKENS'] = '16384'
    os.environ['MAX_TOTAL_TOKENS'] = '4096'
    
    print("=== TOKEN-AWARE BATCHING SIMULATION ===\n")
    
    # Scenario 1: PDF with optimized chunks (1200 chars each)
    print("Scenario 1: PDF with optimized chunks")
    pdf_chunks = [
        "This is a PDF chunk with some formatting artifacts... " * 20,  # ~1200 chars
        "Another PDF chunk with tables and special chars: |---|---| " * 18,  # ~1200 chars  
        "PDF text often has extra whitespace    and   formatting. " * 20,  # ~1200 chars
    ] * 15  # 45 total chunks
    
    simulate_batching_for_texts(pdf_chunks, "PDF chunks")
    
    print("\n" + "="*60 + "\n")
    
    # Scenario 2: Large PDF chunks that exceed individual token limits
    print("Scenario 2: Large PDF chunks exceeding individual limits")
    large_chunks = [
        "Very large PDF chunk with extensive content... " * 100,  # ~4700 chars, ~1500+ tokens
        "Another oversized chunk from a complex PDF document... " * 120,  # ~5600 chars, ~1800+ tokens
    ] * 5  # 10 total oversized chunks
    
    simulate_batching_for_texts(large_chunks, "Oversized PDF chunks")
    
    print("\n" + "="*60 + "\n")
    
    # Scenario 3: Mixed content with varying sizes
    print("Scenario 3: Mixed content sizes")
    mixed_chunks = [
        "Short chunk",  # ~50 chars
        "Medium length chunk with some content here to make it longer than the short one but not too long" * 2,  # ~200 chars
        "Long chunk with extensive content that goes on and on with lots of details and information" * 10,  # ~900 chars
        "Very long PDF-style chunk with formatting artifacts and special characters: |---|---|---| " * 15,  # ~1400 chars
    ] * 8  # 32 total mixed chunks
    
    simulate_batching_for_texts(mixed_chunks, "Mixed content")

def simulate_batching_for_texts(texts, scenario_name):
    """Simulate the batching logic for a list of texts."""
    
    # Calculate statistics
    total_chars = sum(len(text) for text in texts)
    avg_chars = total_chars / len(texts) if texts else 0
    max_chars = max(len(text) for text in texts) if texts else 0
    min_chars = min(len(text) for text in texts) if texts else 0
    
    # Estimate tokens
    estimated_total_tokens = sum(estimate_tokens(text) for text in texts)
    estimated_avg_tokens = estimated_total_tokens / len(texts) if texts else 0
    estimated_max_tokens = max(estimate_tokens(text) for text in texts) if texts else 0
    
    logger.info(f"=== {scenario_name.upper()} ===")
    logger.info(f"Content stats - Total chars: {total_chars:,}, Avg: {avg_chars:.0f}, Min: {min_chars}, Max: {max_chars}")
    logger.info(f"Estimated tokens - Total: {estimated_total_tokens:,}, Avg: {estimated_avg_tokens:.0f}, Max: {estimated_max_tokens}")
    
    # Token limits
    max_batch_tokens = int(os.getenv('MAX_BATCH_TOKENS', '16384'))
    max_total_tokens = int(os.getenv('MAX_TOTAL_TOKENS', '4096'))
    
    # Check for oversized texts
    oversized_texts = [i for i, text in enumerate(texts) if estimate_tokens(text) > max_total_tokens]
    if oversized_texts:
        logger.warning(f"Found {len(oversized_texts)} texts exceeding MAX_TOTAL_TOKENS ({max_total_tokens})")
        for i in oversized_texts[:3]:  # Show first 3
            tokens = estimate_tokens(texts[i])
            logger.warning(f"  Text {i}: {len(texts[i]):,} chars (~{tokens:,} tokens)")
    
    # Calculate token-aware batch size
    if estimated_avg_tokens > 0:
        token_based_batch_size = min(50, max(1, max_batch_tokens // int(estimated_avg_tokens)))
        logger.info(f"Token-aware batching - Max batch tokens: {max_batch_tokens:,}, "
                   f"Avg tokens per text: {estimated_avg_tokens:.0f}, "
                   f"Calculated batch size: {token_based_batch_size}")
    else:
        token_based_batch_size = 25
    
    # Simulate batching
    if len(texts) > token_based_batch_size or estimated_total_tokens > max_batch_tokens:
        logger.info(f"Splitting {len(texts)} texts into token-aware batches")
        
        current_batch = []
        current_batch_tokens = 0
        batch_num = 1
        total_batches_created = 0
        
        for i, text in enumerate(texts):
            text_tokens = estimate_tokens(text)
            
            # Check if adding this text would exceed limits
            if (len(current_batch) >= token_based_batch_size or 
                current_batch_tokens + text_tokens > max_batch_tokens) and current_batch:
                
                # Log current batch
                batch_chars = sum(len(t) for t in current_batch)
                logger.info(f"Batch {batch_num}: {len(current_batch)} texts, "
                           f"{batch_chars:,} chars, ~{current_batch_tokens:,} tokens")
                
                # Reset for next batch
                current_batch = []
                current_batch_tokens = 0
                batch_num += 1
                total_batches_created += 1
            
            current_batch.append(text)
            current_batch_tokens += text_tokens
        
        # Final batch
        if current_batch:
            batch_chars = sum(len(t) for t in current_batch)
            logger.info(f"Final batch {batch_num}: {len(current_batch)} texts, "
                       f"{batch_chars:,} chars, ~{current_batch_tokens:,} tokens")
            total_batches_created += 1
        
        logger.info(f"Total batches created: {total_batches_created}")
        
        # Calculate efficiency
        avg_tokens_per_batch = estimated_total_tokens / total_batches_created if total_batches_created > 0 else 0
        efficiency = (avg_tokens_per_batch / max_batch_tokens) * 100 if max_batch_tokens > 0 else 0
        logger.info(f"Batch efficiency: {efficiency:.1f}% (avg {avg_tokens_per_batch:.0f} tokens per batch)")
        
    else:
        logger.info(f"Single batch sufficient: {len(texts)} texts, ~{estimated_total_tokens:,} tokens")

if __name__ == "__main__":
    simulate_token_aware_batching()
    
    print("\n=== KEY IMPROVEMENTS ===")
    print("1. Token-based batch sizing instead of just character counting")
    print("2. Detection of texts exceeding individual token limits")
    print("3. Smarter token estimation accounting for PDF formatting")
    print("4. Batch efficiency monitoring")
    print("5. Automatic adjustment based on MAX_BATCH_TOKENS and MAX_TOTAL_TOKENS")
    print("\nThis should eliminate 413 errors by respecting LiteLLM's token limits!")