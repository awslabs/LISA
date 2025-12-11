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

import logging
import os
from typing import List

import boto3
import requests
from pydantic import BaseModel, field_validator
from utilities.auth import get_management_key
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config
from utilities.validation import validate_model_name, ValidationError

logger = logging.getLogger(__name__)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)

lisa_api_endpoint = ""


class RagEmbeddings(BaseModel):
    """
    Handles document embeddings through LiteLLM using management credentials.
    """

    model_name: str
    token: str
    lisa_api_endpoint: str
    base_url: str
    cert_path: str | bool

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        validate_model_name(v)
        return v

    def __init__(self, model_name: str, id_token: str | None = None, **data) -> None:
        # Prepare initialization data
        init_data = {"model_name": model_name, **data}
        try:
            # Use management token if id_token is not provided
            if id_token is None:
                logger.info("Using management key for ingestion")
                init_data["token"] = get_management_key()
            else:
                init_data["token"] = id_token

            init_data["lisa_api_endpoint"] = get_rest_api_container_endpoint()
            init_data["base_url"] = get_rest_api_container_endpoint()
            init_data["cert_path"] = get_cert_path(iam_client)

            super().__init__(**init_data)
            logger.info("Successfully initialized pipeline embeddings")
        except Exception:
            logger.error("Failed to initialize pipeline embeddings", exc_info=True)
            raise

    class Config:
        arbitrary_types_allowed = True

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ValidationError: If input texts are invalid
            Exception: If embedding request fails
        """
        if not texts:
            raise ValidationError("No texts provided for embedding")

        # Calculate content statistics for debugging
        total_chars = sum(len(text) for text in texts)
        avg_chars = total_chars / len(texts) if texts else 0
        max_chars = max(len(text) for text in texts) if texts else 0
        min_chars = min(len(text) for text in texts) if texts else 0
        
        # Estimate tokens using more accurate method
        def estimate_tokens(text: str) -> int:
            # More accurate token estimation for embedding models
            # Account for special characters, whitespace, and typical tokenization
            # PDF text often has more tokens per character due to formatting artifacts
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
        
        estimated_total_tokens = sum(estimate_tokens(text) for text in texts)
        estimated_avg_tokens = estimated_total_tokens / len(texts) if texts else 0
        estimated_max_tokens = max(estimate_tokens(text) for text in texts) if texts else 0
        
        logger.info(f"Embedding {len(texts)} documents using {self.model_name}")
        logger.info(f"Content stats - Total chars: {total_chars:,}, Avg: {avg_chars:.0f}, Min: {min_chars}, Max: {max_chars}")
        logger.info(f"Estimated tokens - Total: {estimated_total_tokens:,}, Avg: {estimated_avg_tokens:.0f}, Max: {estimated_max_tokens}")
        
        # Token-aware batching based on LiteLLM limits
        max_batch_tokens = int(os.getenv('MAX_BATCH_TOKENS', '16384'))
        max_total_tokens = int(os.getenv('MAX_TOTAL_TOKENS', '4096'))
        
        # Check for individual texts that exceed token limits
        oversized_texts = [i for i, text in enumerate(texts) if len(text) // 4 > max_total_tokens]
        if oversized_texts:
            logger.warning(f"Found {len(oversized_texts)} texts exceeding MAX_TOTAL_TOKENS ({max_total_tokens})")
            for i in oversized_texts[:5]:  # Log first 5
                logger.warning(f"  Text {i}: {len(texts[i]):,} chars (~{len(texts[i])//4:,} tokens)")
        
        # Calculate token-aware batch size
        if estimated_avg_tokens > 0:
            token_based_batch_size = min(50, max(1, max_batch_tokens // int(estimated_avg_tokens)))
            logger.info(f"Token-aware batching - Max batch tokens: {max_batch_tokens:,}, "
                       f"Avg tokens per text: {estimated_avg_tokens:.0f}, "
                       f"Calculated batch size: {token_based_batch_size}")
        else:
            token_based_batch_size = 25  # Conservative fallback
        
        max_batch_size = token_based_batch_size
        # Use token-aware batching or estimated token limits
        if len(texts) > max_batch_size or estimated_total_tokens > max_batch_tokens:
            logger.info(f"Splitting {len(texts)} texts into token-aware batches of ~{max_batch_size}")
            all_embeddings = []
            
            current_batch = []
            current_batch_tokens = 0
            batch_num = 1
            
            for i, text in enumerate(texts):
                text_tokens = estimate_tokens(text)
                
                # Check if adding this text would exceed limits
                if (len(current_batch) >= max_batch_size or 
                    current_batch_tokens + text_tokens > max_batch_tokens) and current_batch:
                    
                    # Process current batch
                    batch_chars = sum(len(t) for t in current_batch)
                    logger.info(f"Processing token-aware batch {batch_num} - {len(current_batch)} texts, "
                               f"{batch_chars:,} chars, ~{current_batch_tokens:,} tokens")
                    
                    batch_embeddings = self._embed_batch_with_retry(current_batch)
                    all_embeddings.extend(batch_embeddings)
                    
                    # Reset for next batch
                    current_batch = []
                    current_batch_tokens = 0
                    batch_num += 1
                
                current_batch.append(text)
                current_batch_tokens += text_tokens
            
            # Process final batch
            if current_batch:
                batch_chars = sum(len(t) for t in current_batch)
                logger.info(f"Processing final token-aware batch {batch_num} - {len(current_batch)} texts, "
                           f"{batch_chars:,} chars, ~{current_batch_tokens:,} tokens")
                batch_embeddings = self._embed_batch_with_retry(current_batch)
                all_embeddings.extend(batch_embeddings)
            
            return all_embeddings
        else:
            return self._embed_batch_with_retry(texts)

    def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings with automatic retry and batch size reduction for 413 errors.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        max_retries = 3
        current_batch_size = len(texts)
        
        # Log initial batch details
        total_chars = sum(len(text) for text in texts)
        logger.info(f"Starting batch retry logic - {len(texts)} texts, {total_chars:,} total chars")
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0 and current_batch_size > 1:
                    # Reduce batch size on retry for 413 errors
                    current_batch_size = max(1, current_batch_size // 2)
                    logger.warning(f"Attempt {attempt + 1}: Retrying with smaller batch size: {current_batch_size}")
                    
                    if current_batch_size < len(texts):
                        # Split into smaller batches recursively
                        logger.info(f"Splitting {len(texts)} texts into batches of {current_batch_size}")
                        all_embeddings = []
                        for i in range(0, len(texts), current_batch_size):
                            batch_texts = texts[i:i + current_batch_size]
                            batch_chars = sum(len(text) for text in batch_texts)
                            logger.info(f"Retry sub-batch {i//current_batch_size + 1}: {len(batch_texts)} texts, {batch_chars:,} chars")
                            batch_embeddings = self._embed_batch(batch_texts)
                            all_embeddings.extend(batch_embeddings)
                        return all_embeddings
                
                # Try with current batch size
                logger.info(f"Attempting embedding request - {len(texts)} texts, {total_chars:,} chars")
                return self._embed_batch(texts)
                
            except Exception as e:
                if attempt < max_retries and ("413" in str(e) or "Payload Too Large" in str(e)):
                    logger.warning(f"Attempt {attempt + 1} failed with payload size error (batch: {len(texts)} texts, {total_chars:,} chars): {str(e)}")
                    continue
                else:
                    # Re-raise if not a 413 error or max retries exceeded
                    raise

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a single batch of documents.
        
        Args:
            texts: List of text strings to embed (should be <= max_batch_size)
            
        Returns:
            List of embedding vectors
        """
        # Calculate payload size for debugging
        total_chars = sum(len(text) for text in texts)
        import json
        request_data = {"input": texts, "model": self.model_name}
        payload_size = len(json.dumps(request_data).encode('utf-8'))
        
        # Log with safety assessment
        safety_status = "SAFE" if payload_size < 20000 else "RISKY" if payload_size < 30000 else "DANGEROUS"
        logger.info(f"Embedding batch details - Texts: {len(texts)}, Total chars: {total_chars:,}, "
                   f"Payload size: {payload_size:,} bytes [{safety_status}]")
        
        try:
            url = f"{self.base_url}/embeddings"
            response = requests.post(
                url,
                json=request_data,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                verify=self.cert_path,  # Use proper SSL verification
                timeout=300,  # 5 minute timeout
            )

            if response.status_code != 200:
                logger.error(f"Embedding request failed with status {response.status_code}")
                if response.status_code == 413:
                    logger.error("Request payload too large - consider reducing batch size further")
                raise Exception(f"Embedding request failed with status {response.status_code}")

            result = response.json()
            logger.debug(f"API Response: {result}")  # Log the full response for debugging

            # Handle different response formats
            embeddings = []
            if isinstance(result, dict):
                if "data" in result:
                    # OpenAI-style format
                    for item in result["data"]:
                        if isinstance(item, dict) and "embedding" in item:
                            embeddings.append(item["embedding"])
                        else:
                            embeddings.append(item)  # Assume the item itself is the embedding
                else:
                    # Try to find embeddings in the response
                    for key in ["embeddings", "embedding", "vectors", "vector"]:
                        if key in result:
                            embeddings = result[key]
                            break
            elif isinstance(result, list):
                # Direct list format
                embeddings = result

            if not embeddings:
                logger.error(f"Could not find embeddings in response: {result}")
                raise Exception("No embeddings found in API response")

            if len(embeddings) != len(texts):
                logger.error(f"Mismatch between number of texts ({len(texts)}) and embeddings ({len(embeddings)})")
                raise Exception("Number of embeddings does not match number of input texts")

            logger.info(f"Successfully embedded {len(texts)} documents")
            return embeddings

        except requests.Timeout:
            logger.error("Embedding request timed out")
            raise Exception("Embedding request timed out after 5 minutes")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to get embeddings: {str(e)}", exc_info=True)
            raise

    def embed_query(self, text: str) -> List[float]:
        if not text or not isinstance(text, str):
            raise ValidationError("Invalid query text")

        logger.info("Embedding single query text")
        return self.embed_documents([text])[0]
