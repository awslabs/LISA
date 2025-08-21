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

"""Utilities for handling Bedrock Knowledge Base specific operations.

This module centralizes logic related to repositories of type
"bedrock_knowledge_base" so that call sites can remain concise.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

BEDROCK_KB_TYPE = "bedrock_knowledge_base"


def is_bedrock_kb_repository(repository: Dict[str, Any]) -> Any:
    """Return True if the repository is a Bedrock Knowledge Base."""
    return bool(repository.get("type", "") == BEDROCK_KB_TYPE)


def retrieve_documents(
    bedrock_runtime_client: Any,
    repository: Dict[str, Any],
    query: str,
    top_k: int,
    repository_id: str,
) -> List[Dict[str, Any]]:
    """Retrieve documents from Bedrock Knowledge Base.

    Args:
        bedrock_runtime_client: boto3 bedrock-agent-runtime client
        repository: Repository configuration dictionary
        query: Text query to search
        top_k: Number of results to return
        repository_id: Repository identifier to include in metadata

    Returns:
        List of documents in the format expected by callers
    """
    bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})

    response = bedrock_runtime_client.retrieve(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": int(top_k)}},
    )

    docs: List[Dict[str, Any]] = []
    for doc in response.get("retrievalResults", []):
        uri = (doc.get("location", {}) or {}).get("s3Location", {}).get("uri")
        name = uri.split("/")[-1] if uri else None
        docs.append(
            {
                "page_content": (doc.get("content", {}) or {}).get("text", ""),
                "metadata": {
                    "source": uri,
                    "name": name,
                    "repository_id": repository_id,
                },
            }
        )

    return docs


def ingest_document_to_kb(
    s3_client: Any,
    bedrock_agent_client: Any,
    job: Any,
    repository: Dict[str, Any],
) -> None:
    """Copy the source object into the KB datasource bucket and trigger ingestion."""
    bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})

    source_bucket = job.s3_path.split("/")[2]
    s3_client.copy_object(
        CopySource={"Bucket": source_bucket, "Key": job.s3_path.split(source_bucket + "/")[1]},
        Bucket=bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket", None),
        Key=os.path.basename(job.s3_path),
    )
    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
        dataSourceId=bedrock_config.get("bedrockKnowledgeDatasourceId", None),
    )


def delete_document_from_kb(
    s3_client: Any,
    bedrock_agent_client: Any,
    job: Any,
    repository: Dict[str, Any],
) -> None:
    """Remove the source object from the KB datasource bucket and re-sync the KB."""
    bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})

    s3_client.delete_object(
        Bucket=bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket", None),
        Key=os.path.basename(job.s3_path),
    )
    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
        dataSourceId=bedrock_config.get("bedrockKnowledgeDatasourceId", None),
    )
