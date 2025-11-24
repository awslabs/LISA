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
from typing import Any, Dict

from models.domain_objects import IngestionType
from pydantic import BaseModel
from repository.rag_document_repo import RagDocumentRepository

logger = logging.getLogger(__name__)
doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any] | Any:
    """
    Remove LISA-managed documents from repository.

    Only deletes documents with ingestion_type of MANUAL or AUTO.
    Preserves EXISTING documents (user-managed).

    Args:
        event: Event data containing bucket and prefix information
        context: Lambda context

    Returns:
        Dictionary containing array of files with their bucket and key
    """
    repository_id = event.get("repositoryId")
    stack_name = event.get("stackName")
    last_evaluated = event.get("lastEvaluated")

    # Get all documents
    docs, last_evaluated, _ = doc_repo.list_all(repository_id=repository_id, last_evaluated_key=last_evaluated)

    # Filter to LISA-managed only (MANUAL or AUTO)
    lisa_managed = [d for d in docs if d.ingestion_type in [IngestionType.MANUAL, IngestionType.AUTO]]

    logger.info(
        f"Repository cleanup: total={len(docs)}, "
        f"lisa_managed={len(lisa_managed)}, "
        f"preserved={len(docs) - len(lisa_managed)}"
    )

    # Delete from DynamoDB
    for doc in lisa_managed:
        doc_repo.delete_by_id(doc.document_id)

    # Delete from S3 (only LISA-managed)
    doc_repo.delete_s3_docs(repository_id=repository_id, docs=lisa_managed)

    # Ensure JSON-serializable payload for Step Functions when Pydantic models are provided
    serializable_docs = [doc.model_dump() if isinstance(doc, BaseModel) else doc for doc in lisa_managed]
    return {
        "repositoryId": repository_id,
        "stackName": stack_name,
        "documents": serializable_docs,
        "lastEvaluated": last_evaluated,
    }
