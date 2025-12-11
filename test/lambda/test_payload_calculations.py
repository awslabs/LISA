#!/usr/bin/env python3
"""
Test script to verify payload size calculations match observed behavior.
"""

import json

def estimate_payload_size(texts, model_name="e5-large-v2"):
    """Estimate the JSON payload size for an embedding request."""
    request_data = {"input": texts, "model": model_name}
    payload_bytes = len(json.dumps(request_data).encode('utf-8'))
    return payload_bytes

def test_observed_limits():
    """Test the observed 17K success / 36K failure limits."""
    
    print("=== PAYLOAD SIZE ANALYSIS ===\n")
    
    # Simulate texts of different lengths
    test_cases = [
        ("Short chunks (300 chars)", ["x" * 300] * 50),
        ("Medium chunks (800 chars)", ["x" * 800] * 20),  
        ("Long chunks (1200 chars)", ["x" * 1200] * 15),
        ("Very long chunks (2000 chars)", ["x" * 2000] * 9),
        ("Observed SUCCESS case", ["x" * 850] * 20),  # ~17K chars
        ("Observed FAILURE case", ["x" * 900] * 40),  # ~36K chars
    ]
    
    for description, texts in test_cases:
        total_chars = sum(len(text) for text in texts)
        payload_bytes = estimate_payload_size(texts)
        
        # Determine safety level
        if payload_bytes < 20000:
            safety = "SAFE ✅"
        elif payload_bytes < 30000:
            safety = "RISKY ⚠️"
        else:
            safety = "DANGEROUS ❌"
            
        print(f"{description}:")
        print(f"  Texts: {len(texts)}")
        print(f"  Total chars: {total_chars:,}")
        print(f"  Payload size: {payload_bytes:,} bytes")
        print(f"  Safety: {safety}")
        print()

def calculate_safe_batch_sizes():
    """Calculate safe batch sizes for different text lengths."""
    
    print("=== SAFE BATCH SIZE CALCULATIONS ===\n")
    
    MAX_PAYLOAD_CHARS = 15000  # Conservative limit
    
    text_lengths = [300, 500, 800, 1000, 1200, 1500, 2000]
    
    print(f"Target payload limit: {MAX_PAYLOAD_CHARS:,} characters\n")
    
    for avg_length in text_lengths:
        safe_batch_size = max(1, int(MAX_PAYLOAD_CHARS / avg_length))
        estimated_chars = safe_batch_size * avg_length
        estimated_payload = estimate_payload_size(["x" * avg_length] * safe_batch_size)
        
        print(f"Avg text length: {avg_length:,} chars")
        print(f"  Safe batch size: {safe_batch_size} texts")
        print(f"  Estimated chars: {estimated_chars:,}")
        print(f"  Estimated payload: {estimated_payload:,} bytes")
        print()

if __name__ == "__main__":
    test_observed_limits()
    calculate_safe_batch_sizes()
    
    print("=== RECOMMENDATIONS ===")
    print("1. Use MAX_EMBEDDING_PAYLOAD_CHARS=15000 for safety")
    print("2. Monitor payload sizes in logs")
    print("3. Adjust limits based on your specific API behavior")
    print("4. The system will automatically calculate safe batch sizes")