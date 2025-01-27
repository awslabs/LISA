
import logging
import os
from .lambda_functions import RagDocumentRepository, get_embeddings_pipeline, get_vector_store_client, RagDocument
from utilities.validation import ValidationError
from langchain_core.vectorstores import VectorStore


logger = logging.getLogger(__name__)

doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])


def lambda_handler(event: dict[str, any], context: any) -> dict[str, any]:
    """"Lambda function to delete a document from the repository.

    Args:
        event (dict[str, any]): Lambda event object.
        context (any): Lambda context object.

    Returns:
        dict[str, any]: Lambda response object.
    """
    logger.info(f"Lambda function started. Event: {event}")

    try:
        # Get document location from event
        if "bucket" not in event or "key" not in event:
            raise ValidationError("Missing required fields: bucket and key")

        bucket = event.get("bucket")
        key = event.get("key")
        s3_key = f"s3://{bucket}/{key}"

        collection_id = os.environ["EMBEDDING_MODEL"]
        repository_id = os.environ["REPOSITORY_ID"]

        logger.info(f"Deleting document {s3_key} for repository {repository_id}")
        docs: list[RagDocument.model_dump] = doc_repo.find_by_source(repository_id=repository_id, collection_id=collection_id, document_source=s3_key)
        if len(docs) == 0:
            raise ValidationError(f"Document {s3_key} not found in repository {repository_id}/{collection_id}")

        vs = _get_vs(repository_id=repository_id, collection_id=collection_id)

        for doc in docs:
            logging.info(f"Removing {doc.get('chunks')} chunks for document: {doc.get('document_name')}({doc.get('source')})")
            vs.delete(ids=doc.get("subdocs"))

        for doc in docs:
            doc_repo.delete_by_id(repository_id=repository_id, document_id=doc.get("document_id"))

        logger.info(f"Successfully removed {s3_key} from vector store {repository_id}/{collection_id}")

        return {
            "statusCode": 200,
            "body": {
                "message": f"Successfully removed {s3_key} from vector store {repository_id}/{collection_id}"
            }
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


def _get_vs(repository_id:str, collection_id:str)-> VectorStore:
    embeddings = get_embeddings_pipeline(model_name=collection_id)

    # Initialize vector store using model name as index, matching lambda_functions.py pattern
    vs = get_vector_store_client(
        repository_id,
        index=collection_id,
        embeddings=embeddings,
    )

    return vs

