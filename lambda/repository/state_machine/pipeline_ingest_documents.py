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
"""Lambda handlers for PipelineIngestDocuments state machine."""

import os
from typing import Any, Dict

import boto3
from models.document_processor import DocumentProcessor
from models.vectorstore import VectorStore


def handle_pipeline_ingest_documents(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process a single document from the Map state by chunking and storing in vectorstore.

    Args:
        event: Event containing the document bucket and key
        context: Lambda context

    Returns:
        Dictionary indicating success/failure
    """
    try:
        # Get document location from event
        bucket = event["bucket"]
        key = event["key"]

        # Get configuration from environment variables
        chunk_size = int(os.environ["CHUNK_SIZE"])
        chunk_overlap = int(os.environ["CHUNK_OVERLAP"])
        embedding_model = os.environ["EMBEDDING_MODEL"]
        collection_name = os.environ["COLLECTION_NAME"]

        # Initialize document processor and vectorstore
        doc_processor = DocumentProcessor()
        vectorstore = VectorStore(collection_name=collection_name, embedding_model=embedding_model)

        # Download and process document
        s3_client = boto3.client("s3")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")

        # Chunk document
        chunks = doc_processor.chunk_text(text=content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # Store chunks in vectorstore
        vectorstore.add_texts(texts=chunks, metadata={"source": f"s3://{bucket}/{key}"})

        return {
            "statusCode": 200,
            "body": {
                "message": f"Successfully processed document s3://{bucket}/{key}",
                "chunks_processed": len(chunks),
            },
        }

    except Exception as e:
        print(f"Error processing document: {str(e)}")
        raise
