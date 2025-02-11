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
from typing import Any

from langchain_core.vectorstores import VectorStore
from utilities.validation import ValidationError

from .lambda_functions import get_embeddings_pipeline, get_vector_store_client, RagDocument, RagDocumentRepository

logger = logging.getLogger(__name__)

doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])

"""
Pipeline Delete Document Lambda Handler

This module provides functionality to delete documents from a RAG (Retrieval-Augmented Generation)
repository and its associated vector store. It handles the cleanup of both the document metadata
and its vector embeddings.

Environment Variables Required:
    RAG_DOCUMENT_TABLE: DynamoDB table name for storing document metadata
    RAG_SUB_DOCUMENT_TABLE: DynamoDB table name for storing sub-document metadata
    EMBEDDING_MODEL: Identifier for the embedding model being used
    REPOSITORY_ID: Identifier for the current repository

Dependencies:
    - langchain_core.vectorstores
    - utilities.validation
    - lambda_functions (local module)
"""


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for processing document deletion requests.

    This function:
    1. Extracts document location information from the event
    2. Finds the document in the repository
    3. Removes the document's vectors from the vector store
    4. Deletes the document metadata from the repository

    Args:
        event (dict[str, Any]): Lambda event containing:
            - bucket: S3 bucket name
            - key: Object key in the bucket
            - prefix: (optional) S3 key prefix, defaults to "/"
        context (Any): Lambda context object

    Returns:
        dict[str, Any]: Response object containing:
            - statusCode: HTTP status code
            - body: Message indicating success or failure

    Raises:
        Exception: If validation fails or processing encounters an error
    """
    logger.info(f"Lambda function started. Event: {event}")

    try:
        # Get document location from event
        if "bucket" not in event or "key" not in event:
            raise ValidationError("Missing required fields: bucket and key")

        bucket = event.get("bucket")
        key = event.get("key")
        prefix = event.get("prefix", "/")
        s3_key = f"s3://{bucket}{prefix}{key}"

        pipelineConfig = event.get("pipelineConfig", {})
        collection_id = pipelineConfig.get("embeddingModel")
        repository_id = pipelineConfig.get("repositoryId")

        logger.info(f"Deleting document {s3_key} for repository {repository_id}")
        docs: list[RagDocument.model_dump] = doc_repo.find_by_source(
            repository_id=repository_id, collection_id=collection_id, document_source=s3_key
        )
        if len(docs) == 0:
            msg = "Document {s3_key} not found in repository {repository_id}/{collection_id}. Ignoring deletion"
            logging.error(msg)
            return {
                "statusCode": 404,
                "body": {"message": msg},
            }

        vs = _get_vs(repository_id=repository_id, collection_id=collection_id)

        for doc in docs:
            logging.info(
                f"Removing {doc.get('chunks')} chunks for document: {doc.get('document_name')}({doc.get('source')})"
            )
            vs.delete(ids=doc.get("subdocs"))

        for doc in docs:
            doc_repo.delete_by_id(repository_id=repository_id, document_id=doc.get("document_id"))

        logger.info(f"Successfully removed {s3_key} from vector store {repository_id}/{collection_id}")

        return {
            "statusCode": 200,
            "body": {"message": f"Successfully removed {s3_key} from vector store {repository_id}/{collection_id}"},
        }
    except ValidationError as e:
        # For validation errors, raise with clear message
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        # For all other errors, log and re-raise to signal failure
        error_msg = f"Failed to delete document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)


def _get_vs(repository_id: str, collection_id: str) -> VectorStore:
    """
    Helper function to initialize and return a vector store client.

    Args:
        repository_id (str): Identifier for the repository
        collection_id (str): Identifier for the collection/model

    Returns:
        VectorStore: Initialized vector store client
    """
    embeddings = get_embeddings_pipeline(model_name=collection_id)

    # Initialize vector store using model name as index, matching lambda_functions.py pattern
    vs = get_vector_store_client(
        repository_id,
        index=collection_id,
        embeddings=embeddings,
    )

    return vs
