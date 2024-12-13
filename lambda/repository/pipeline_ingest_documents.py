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

"""Lambda function for pipeline document ingestion."""

import logging
import os
from typing import Any, Dict, List

import boto3
from utilities.common_functions import retry_config
from utilities.file_processing import process_record
from utilities.validation import validate_chunk_params, validate_model_name, validate_repository_type, ValidationError
from utilities.vector_store import get_vector_store_client

from .lambda_functions import _get_embeddings_pipeline

logger = logging.getLogger(__name__)
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


def batch_texts(texts: List[str], metadatas: List[Dict], batch_size: int = 500) -> list[tuple[list[str], list[dict]]]:
    """
    Split texts and metadata into batches of specified size.

    Args:
        texts: List of text strings to batch
        metadatas: List of metadata dictionaries
        batch_size: Maximum size of each batch
    Returns:
        List of tuples containing (texts_batch, metadatas_batch)
    """
    batches = []
    for i in range(0, len(texts), batch_size):
        text_batch = texts[i : i + batch_size]
        metadata_batch = metadatas[i : i + batch_size]
        batches.append((text_batch, metadata_batch))
    return batches


def handle_pipeline_ingest_documents(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle pipeline document ingestion.

    Process a single document from the Map state by chunking and storing in vectorstore.
    Reuses existing document processing and vectorstore infrastructure.
    Configuration is provided through environment variables set by the state machine.

    Args:
        event: Event containing the document bucket and key
        context: Lambda context

    Returns:
        Dictionary with status code and response body

    Raises:
        Exception: For any error to signal failure to Step Functions
    """
    try:
        # Get document location from event
        if "bucket" not in event or "key" not in event:
            raise ValidationError("Missing required fields: bucket and key")

        bucket = event["bucket"]
        key = event["key"]
        s3_key = f"s3://{bucket}/{key}"

        # Get all configuration from environment variables
        required_env_vars = ["CHUNK_SIZE", "CHUNK_OVERLAP", "EMBEDDING_MODEL", "REPOSITORY_TYPE", "REPOSITORY_ID"]
        missing_vars = [var for var in required_env_vars if var not in os.environ]
        if missing_vars:
            raise ValidationError(f"Missing required environment variables: {', '.join(missing_vars)}")

        chunk_size = int(os.environ["CHUNK_SIZE"])
        chunk_overlap = int(os.environ["CHUNK_OVERLAP"])
        embedding_model = os.environ["EMBEDDING_MODEL"]
        repository_type = os.environ["REPOSITORY_TYPE"]
        repository_id = os.environ["REPOSITORY_ID"]

        # Validate inputs
        validate_model_name(embedding_model)
        validate_repository_type(repository_type)
        validate_chunk_params(chunk_size, chunk_overlap)

        logger.info(f"Processing document {s3_key} for repository {repository_id} of type {repository_type}")

        # Process document using existing utilities, passing the bucket explicitly
        docs = process_record(
            s3_keys=[key],  # Changed from s3_key to just key since process_record expects just the key
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            bucket=bucket,  # Pass the bucket explicitly
        )

        if not docs or not docs[0]:
            raise ValidationError(f"No content extracted from document {s3_key}")

        # Prepare texts and metadata
        texts = []
        metadatas = []
        for doc_list in docs:
            for doc in doc_list:
                texts.append(doc.page_content)
                # Add repository ID to metadata
                doc.metadata["repository_id"] = repository_id
                metadatas.append(doc.metadata)

        # Get embeddings using pipeline-specific function that uses IAM auth
        embeddings = _get_embeddings_pipeline(model_name=embedding_model)

        # Initialize vector store using model name as index, matching lambda_functions.py pattern
        vs = get_vector_store_client(
            repository_id,
            index=embedding_model,  # Use model name as index to match lambda_functions.py
            embeddings=embeddings,
        )

        # Process documents in batches
        all_ids = []
        batches = batch_texts(texts, metadatas)
        total_batches = len(batches)

        logger.info(f"Processing {len(texts)} texts in {total_batches} batches")

        for i, (text_batch, metadata_batch) in enumerate(batches, 1):
            logger.info(f"Processing batch {i}/{total_batches} with {len(text_batch)} texts")
            batch_ids = vs.add_texts(texts=text_batch, metadatas=metadata_batch)
            if not batch_ids:
                raise Exception(f"Failed to store documents in vector store for batch {i}")
            all_ids.extend(batch_ids)
            logger.info(f"Successfully processed batch {i}")

        if not all_ids:
            raise Exception("Failed to store any documents in vector store")

        logger.info(f"Successfully processed {len(all_ids)} chunks from {s3_key} for repository {repository_id}")

        return {
            "message": f"Successfully processed document {s3_key}",
            "repository_id": repository_id,
            "repository_type": repository_type,
            "chunks_processed": len(all_ids),
            "document_ids": all_ids,
        }

    except ValidationError as e:
        # For validation errors, raise with clear message
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        # For all other errors, log and re-raise to signal failure
        error_msg = f"Failed to process document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
