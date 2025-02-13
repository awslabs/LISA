import logging
import os
from typing import Any, Dict

from repository.rag_document_repo import RagDocumentRepository

logger = logging.getLogger(__name__)
doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any] | Any:
    """
    Remove documents associated with a repository
    Args:
        event: Event data containing bucket and prefix information
        context: Lambda context

    Returns:
        Dictionary containing array of files with their bucket and key
    """
    repository_id = event.get("repositoryId")
    stack_name = event.get("stackName")
    last_evaluated = event.get("lastEvaluated")

    docs, last_evaluated = doc_repo.list_all(
        repository_id=repository_id, last_evaluated_key=last_evaluated
    )
    for doc in docs:
        doc_repo.delete_by_id(repository_id=repository_id, document_id=doc.get("document_id"))

    doc_repo.delete_s3_docs(repository_id=repository_id, docs=docs)

    return {"repositoryId": repository_id, "stackName": stack_name, "documents": docs, "lastEvaluated": last_evaluated}
