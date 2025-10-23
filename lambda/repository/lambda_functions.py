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

"""Lambda functions for RAG repository API."""
import json
import logging
import os
import urllib.parse
from typing import Any, cast, Dict, List, Optional

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.config import Config
from models.domain_objects import (
    CollectionSortBy,
    CollectionStatus,
    CreateCollectionRequest,
    FixedChunkingStrategy,
    IngestionJob,
    IngestionStatus,
    ListJobsResponse,
    PaginationParams,
    PaginationResult,
    RagDocument,
    SortOrder,
    UpdateCollectionRequest,
)
from repository.collection_service import CollectionService
from repository.config.params import ListJobsParams
from repository.embeddings import RagEmbeddings
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.auth import admin_only, get_user_context, get_username, is_admin
from utilities.bedrock_kb import retrieve_documents
from utilities.common_functions import api_wrapper, get_groups, get_id_token, retry_config, user_has_group_access
from utilities.exceptions import HTTPException
from utilities.repository_types import RepositoryType
from utilities.validation import ValidationError
from utilities.vector_store import get_vector_store_client

logger = logging.getLogger(__name__)
region_name = os.environ["AWS_REGION"]
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name, config=retry_config)
iam_client = boto3.client("iam", region_name, config=retry_config)
step_functions_client = boto3.client("stepfunctions", region_name, config=retry_config)
ddb_client = boto3.client("dynamodb", region_name, config=retry_config)
bedrock_client = boto3.client("bedrock-agent-runtime", region_name, config=retry_config)
s3 = session.client(
    "s3",
    region_name,
    config=Config(
        retries={
            "max_attempts": 3,
            "mode": "standard",
        },
        signature_version="s3v4",
    ),
)
doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])
vs_repo = VectorStoreRepository()
ingestion_service = DocumentIngestionService()
ingestion_job_repository = IngestionJobRepository()
collection_service = CollectionService()


@api_wrapper
def list_all(event: dict, context: dict) -> List[Dict[str, Any]]:
    """
    List all available repositories that the user has access to.

    Args:
        event: Lambda event containing user authentication
        context: Lambda context

    Returns:
        List of repository configurations user can access
    """
    user_groups = get_groups(event)
    registered_repositories = vs_repo.get_registered_repositories()
    admin_override = is_admin(event)
    return [
        repo
        for repo in registered_repositories
        if admin_override or user_has_group_access(user_groups, repo.get("allowedGroups", []))
    ]


@api_wrapper
@admin_only
def list_status(event: dict, context: dict) -> dict[str, Any]:
    """
    Get all repository status.

    Returns:
        List of repository status
    """
    return cast(dict, vs_repo.get_repository_status())


@api_wrapper
def similarity_search(event: dict, context: dict) -> Dict[str, Any]:
    """Return documents matching the query.

    Conducts similarity search against the vector store returning the top K
    documents based on the specified query.

    Args:
        event (dict): The Lambda event object containing:
            - queryStringParameters.modelName (optional): Name of the embedding model
              (not needed if collectionId provided)
            - queryStringParameters.collectionId (optional): Collection ID to search within
            - queryStringParameters.query: Search query text
            - queryStringParameters.repositoryType: Type of repository
            - queryStringParameters.topK (optional): Number of results to return (default: 3)
            - queryStringParameters.score (optional): Include similarity scores (default: false)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing:
            - docs: List of matching documents with their content and metadata

    Raises:
        ValidationError: If required parameters are missing or invalid
    """
    query_string_params = event["queryStringParameters"]
    query = query_string_params["query"]
    top_k = query_string_params.get("topK", 3)
    include_score = query_string_params.get("score", "false").lower() == "true"
    repository_id = event["pathParameters"]["repositoryId"]
    collection_id = query_string_params.get("collectionId")

    repository = get_repository(event, repository_id=repository_id)

    # Get user context for collection access
    username = get_username(event)
    user_groups = get_groups(event)
    admin = is_admin(event)

    # Determine embedding model
    model_name = None
    if collection_id:
        # Get embedding model from collection
        try:
            collection = collection_service.get_collection(
                collection_id=collection_id,
                repository_id=repository_id,
                user_id=username,
                user_groups=user_groups,
                is_admin=admin,
            )
            model_name = (
                collection.embeddingModel
                if hasattr(collection, "embeddingModel") and collection.embeddingModel
                else repository.get("embeddingModelId")
            )
            logger.info(f"Using embedding model from collection: {model_name}")
        except Exception as e:
            logger.warning(f"Failed to get collection {collection_id}: {e}, falling back to modelName parameter")
            model_name = query_string_params.get("modelName")
    else:
        # Use modelName from query parameters
        model_name = query_string_params.get("modelName")

    if not model_name:
        raise ValidationError("modelName is required when collectionId is not provided")

    id_token = get_id_token(event)

    docs: List[Dict[str, Any]] = []
    if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
        docs = retrieve_documents(
            bedrock_runtime_client=bedrock_client,
            repository=repository,
            query=query,
            top_k=int(top_k),
            repository_id=repository_id,
        )
    else:
        # Use collection_id as index if provided, otherwise use model_name
        index_name = collection_id if collection_id else model_name
        logger.info(f"Searching in index: {index_name} with embedding model: {model_name}")
        embeddings = RagEmbeddings(model_name=model_name, id_token=id_token)
        vs = get_vector_store_client(repository_id, index=index_name, embeddings=embeddings)

        # empty vector stores do not have an initialize index. Return empty docs
        if RepositoryType.is_type(repository, RepositoryType.OPENSEARCH) and not vs.client.indices.exists(
            index=index_name
        ):
            logger.info(f"Index {index_name} does not exist. Returning empty docs.")
        else:
            docs = (
                _similarity_search_with_score(vs, query, top_k, repository)
                if include_score
                else _similarity_search(vs, query, top_k)
            )
    doc_content = [
        {
            "Document": {
                "page_content": doc.get("page_content", ""),
                "metadata": doc.get("metadata", {}),
            }
        }
        for doc in docs
    ]

    doc_return = {"docs": doc_content}
    logger.info(f"Returning: {doc_return}")
    return doc_return


def get_repository(event: dict[str, Any], repository_id: str) -> None:
    repo = vs_repo.find_repository_by_id(repository_id)
    """Ensures a user has access to the repository or else raises an HTTPException"""
    if is_admin(event) is False:
        user_groups = json.loads(event["requestContext"]["authorizer"]["groups"]) or []
        if not user_has_group_access(user_groups, repo.get("allowedGroups", [])):
            raise HTTPException(status_code=403, message="User does not have permission to access this repository")
    return repo


@api_wrapper
def create_collection(event: dict, context: dict) -> Dict[str, Any]:
    """
    Create a new collection within a vector store.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - body: JSON with collection configuration (CreateCollectionRequest)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing the created collection configuration

    Raises:
        ValidationError: If validation fails or user lacks permission
        HTTPException: If repository not found or access denied
    """
    # Extract path parameters
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    if not repository_id:
        raise ValidationError("repositoryId is required")

    # Parse request body
    try:
        body = json.loads(event.get("body", {}))
        request = CreateCollectionRequest(**body)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in request body: {e}")
    except Exception as e:
        raise ValidationError(f"Invalid request: {e}")

    # Get user context
    username = get_username(event)
    user_groups = get_groups(event)
    admin = is_admin(event)

    # Ensure repository exists and user has access
    _ = get_repository(event, repository_id=repository_id)

    # Create collection via service
    collection = collection_service.create_collection(
        request=request,
        repository_id=repository_id,
        user_id=username,
        user_groups=user_groups,
        is_admin=admin,
    )

    # Return collection configuration
    return collection.model_dump(mode="json")


@api_wrapper
def get_collection(event: dict, context: dict) -> Dict[str, Any]:
    """
    Get a collection by ID within a vector store.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - pathParameters.collectionId: The collection ID
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing the collection configuration

    Raises:
        ValidationError: If collection not found or user lacks permission
        HTTPException: If repository not found or access denied
    """
    # Extract path parameters
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")
    collection_id = path_params.get("collectionId")

    if not repository_id:
        raise ValidationError("repositoryId is required")
    if not collection_id:
        raise ValidationError("collectionId is required")

    # Get user context
    username = get_username(event)
    user_groups = get_groups(event)
    admin = is_admin(event)

    # Ensure repository exists and user has access
    _ = get_repository(event, repository_id=repository_id)

    # Get collection via service (includes access control check)
    collection = collection_service.get_collection(
        collection_id=collection_id,
        repository_id=repository_id,
        user_id=username,
        user_groups=user_groups,
        is_admin=admin,
    )

    # Return collection configuration
    return collection.model_dump(mode="json")


@api_wrapper
def update_collection(event: dict, context: dict) -> Dict[str, Any]:
    """
    Update a collection within a vector store.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - pathParameters.collectionId: The collection ID
            - body: JSON with partial collection updates (UpdateCollectionRequest)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing:
            - collection: The updated collection configuration
            - warnings: List of warning messages (e.g., chunking strategy changes)

    Raises:
        ValidationError: If validation fails or user lacks permission
        HTTPException: If repository or collection not found or access denied
    """
    # Extract path parameters
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")
    collection_id = path_params.get("collectionId")

    if not repository_id:
        raise ValidationError("repositoryId is required")
    if not collection_id:
        raise ValidationError("collectionId is required")

    # Parse request body
    try:
        body = json.loads(event.get("body", {}))
        request = UpdateCollectionRequest(**body)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in request body: {e}")
    except Exception as e:
        raise ValidationError(f"Invalid request: {e}")

    # Get user context
    username = get_username(event)
    user_groups = get_groups(event)
    admin = is_admin(event)

    # Ensure repository exists and user has access
    _ = get_repository(event, repository_id=repository_id)

    # Update collection via service (includes access control check)
    updated_collection, warnings = collection_service.update_collection(
        collection_id=collection_id,
        repository_id=repository_id,
        request=request,
        user_id=username,
        user_groups=user_groups,
        is_admin=admin,
    )

    # Build response
    response = {
        "collection": updated_collection.model_dump(mode="json"),
    }

    # Include warnings if any
    if warnings:
        response["warnings"] = warnings

    return response


@api_wrapper
def delete_collection(event: dict, context: dict) -> Dict[str, Any]:
    """
    Delete a collection within a vector store.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - pathParameters.collectionId: The collection ID
            - queryStringParameters.hardDelete (optional): Whether to hard delete (default: false)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: Empty dictionary (204 No Content)

    Raises:
        ValidationError: If validation fails or user lacks permission
        HTTPException: If repository or collection not found or access denied
    """
    # Extract path parameters
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")
    collection_id = path_params.get("collectionId")

    if not repository_id:
        raise ValidationError("repositoryId is required")
    if not collection_id:
        raise ValidationError("collectionId is required")

    # Get user context
    username = get_username(event)
    user_groups = get_groups(event)
    admin = is_admin(event)

    # Ensure repository exists and user has access
    _ = get_repository(event, repository_id=repository_id)

    # Delete collection via service (includes access control check)
    collection_service.delete_collection(
        collection_id=collection_id,
        repository_id=repository_id,
        user_id=username,
        user_groups=user_groups,
        is_admin=admin,
    )

    # Return empty response for 204 No Content
    return {}


@api_wrapper
def list_collections(event: dict, context: dict) -> Dict[str, Any]:
    """
    List collections in a repository with pagination, filtering, and sorting.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - queryStringParameters.page: Page number (optional, default: 1)
            - queryStringParameters.pageSize: Items per page (optional, default: 20, max: 100)
            - queryStringParameters.filter: Text filter for name/description (optional)
            - queryStringParameters.status: Status filter (ACTIVE, ARCHIVED, DELETED) (optional)
            - queryStringParameters.sortBy: Sort field (name, createdAt, updatedAt) (optional, default: createdAt)
            - queryStringParameters.sortOrder: Sort order (asc, desc) (optional, default: desc)
            - queryStringParameters.lastEvaluatedKey*: Pagination token fields (optional)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing:
            - collections: List of collection configurations
            - pagination: Pagination metadata (totalCount, currentPage, totalPages)
            - lastEvaluatedKey: Pagination token for next page
            - hasNextPage: Whether there are more pages
            - hasPreviousPage: Whether there is a previous page

    Raises:
        ValidationError: If validation fails or user lacks permission
        HTTPException: If repository not found or access denied
    """
    # Extract path parameters
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    if not repository_id:
        raise ValidationError("repositoryId is required")

    # Get user context
    username = get_username(event)
    user_groups = get_groups(event)
    admin = is_admin(event)

    # Ensure repository exists and user has access
    _ = get_repository(event, repository_id=repository_id)

    # Parse query parameters
    query_params = event.get("queryStringParameters", {}) or {}

    # Parse pagination parameters
    page_size = PaginationParams.parse_page_size(query_params, default=20, max_size=100)

    # Parse last evaluated key if present
    last_evaluated_key = None
    if "lastEvaluatedKeyCollectionId" in query_params:
        last_evaluated_key = {
            "collectionId": urllib.parse.unquote(query_params["lastEvaluatedKeyCollectionId"]),
            "repositoryId": urllib.parse.unquote(query_params.get("lastEvaluatedKeyRepositoryId", repository_id)),
        }
        # Add additional keys based on the index being used
        if "lastEvaluatedKeyStatus" in query_params:
            last_evaluated_key["status"] = urllib.parse.unquote(query_params["lastEvaluatedKeyStatus"])
        if "lastEvaluatedKeyCreatedAt" in query_params:
            last_evaluated_key["createdAt"] = urllib.parse.unquote(query_params["lastEvaluatedKeyCreatedAt"])

    # Parse filter parameters
    filter_text = query_params.get("filter")

    # Parse status filter
    status_filter = None
    if "status" in query_params:
        try:
            status_filter = CollectionStatus(query_params["status"])
        except ValueError:
            raise ValidationError(f"Invalid status value: {query_params['status']}")

    # Parse sort parameters
    sort_by = CollectionSortBy.CREATED_AT
    if "sortBy" in query_params:
        try:
            sort_by = CollectionSortBy(query_params["sortBy"])
        except ValueError:
            raise ValidationError(f"Invalid sortBy value: {query_params['sortBy']}")

    sort_order = SortOrder.DESC
    if "sortOrder" in query_params:
        try:
            sort_order = SortOrder(query_params["sortOrder"])
        except ValueError:
            raise ValidationError(f"Invalid sortOrder value: {query_params['sortOrder']}")

    # List collections via service (includes access control filtering)
    collections, next_key = collection_service.list_collections(
        repository_id=repository_id,
        user_id=username,
        user_groups=user_groups,
        is_admin=admin,
        page_size=page_size,
        last_evaluated_key=last_evaluated_key,
        filter_text=filter_text,
        status_filter=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Calculate pagination metadata
    pagination_result = PaginationResult.from_keys(
        original_key=last_evaluated_key,
        returned_key=next_key,
    )

    # Get total count (optional - can be expensive for large datasets)
    total_count = None
    current_page = None
    total_pages = None

    # Only calculate total count if no filters are applied (for performance)
    if not filter_text and not status_filter:
        try:
            from repository.collection_repo import CollectionRepository

            repo = CollectionRepository()
            total_count = repo.count_by_repository(repository_id)

            # Calculate page numbers if we have total count
            if total_count is not None:
                total_pages = (total_count + page_size - 1) // page_size
                # Estimate current page based on whether we have a last_evaluated_key
                current_page = 1 if not last_evaluated_key else None
        except Exception as e:
            logger.warning(f"Failed to get total count for repository {repository_id}: {e}")

    # Build response
    response = {
        "collections": [c.model_dump(mode="json") for c in collections],
        "pagination": {
            "totalCount": total_count,
            "currentPage": current_page,
            "totalPages": total_pages,
        },
        "lastEvaluatedKey": next_key,
        "hasNextPage": pagination_result.has_next_page,
        "hasPreviousPage": pagination_result.has_previous_page,
    }

    return response


def _ensure_document_ownership(event: dict[str, Any], docs: list[RagDocument]) -> None:
    """Verify ownership of documents"""
    username = get_username(event)
    if is_admin(event) is False:
        for doc in docs:
            if not (doc.username == username):
                raise ValueError(f"Document {doc.document_id} is not owned by {username}")


@api_wrapper
def delete_documents(event: dict, context: dict) -> Dict[str, Any]:
    """Purge all records related to the specified document from the RAG repository. If a documentId is supplied, a
    single document will be removed. If a documentName is supplied, all documents with that name will be removed

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository id of VectorStore
            - queryStringParameters.collectionId: The collection identifier
            - queryStringParameters.repositoryType: Type of repository of VectorStore
            - queryStringParameters.documentIds (optional): Array of document IDs to purge
            - queryStringParameters.documentName (optional): Name of document to purge
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing:
            - documentName (str): Name of the purged document
            - recordsPurged (int): Number of records purged from VectorStore

    Raises:
        ValueError: If document is not found in repository
    """
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")
    query_string_params = event.get("queryStringParameters", {}) or {}
    collection_id = query_string_params.get("collectionId", None)
    body = json.loads(event.get("body", ""))
    document_ids = body.get("documentIds", None)

    if not document_ids:
        raise ValidationError("No 'documentIds' parameter supplied")

    # Ensure repo access
    _ = get_repository(event, repository_id=repository_id)

    rag_documents: list[RagDocument] = []
    if document_ids:
        rag_documents = [doc_repo.find_by_id(document_id=document_id) for document_id in document_ids]

    if not rag_documents:
        raise ValueError(f"No documents found in repository collection {repository_id}:{collection_id}")

    _ensure_document_ownership(event, rag_documents)

    # todo don't delete object from s3 if still referenced by another repository/collection
    # delete s3 files if
    doc_repo.delete_s3_docs(repository_id, rag_documents)

    jobs = []
    for rag_document in rag_documents:
        logger.info(f"Deleting document {rag_document.model_dump()}")

        # lookup previous ingestion job, or create one (if document was ingested before batch was implemented)
        ingestion_job = ingestion_job_repository.find_by_document(rag_document.document_id)
        if ingestion_job is None:
            ingestion_job = IngestionJob(
                document_id=rag_document.document_id,
                repository_id=rag_document.repository_id,
                collection_id=rag_document.collection_id,
                chunk_strategy=None,
                s3_path=rag_document.source,
                username=rag_document.username,
                status=IngestionStatus.DELETE_PENDING,
            )

        ingestion_job_repository.save(ingestion_job)
        ingestion_service.create_delete_job(ingestion_job)
        logger.info(f"Deleting document {rag_document.source} for repository {rag_document.repository_id}")

        jobs.append(
            {
                "jobId": ingestion_job.id,
                "documentId": ingestion_job.document_id,
                "status": ingestion_job.status,
                "s3Path": ingestion_job.s3_path,
            }
        )

    return {"jobs": jobs}


@api_wrapper
def ingest_documents(event: dict, context: dict) -> dict:
    """Ingest documents into the RAG repository with collection support.

    Args:
        event (dict): The Lambda event object containing:
            - body.embeddingModel.modelName: Embedding model name (for backward compatibility)
            - body.keys: List of s3 keys to ingest
            - body.collectionId (optional): Target collection ID
            - body.chunkingStrategy (optional): Override chunking strategy (if allowed)
            - body.metadata (optional): Additional metadata tags
            - pathParameters.repositoryId: Repository id (VectorStore)
            - queryStringParameters.repositoryType: Repository type (VectorStore)
            - queryStringParameters.chunkSize (optional): Size of text chunks (legacy)
            - queryStringParameters.chunkOverlap (optional): Overlap between chunks (legacy)
        context (dict): The Lambda context object

    Returns:
        dict: A dictionary containing:
            - ingestionJobIds (list): List of generated ingestion job IDs
            - collectionId (str): The collection ID used for ingestion
            - collectionName (str): The collection name

    Raises:
        ValidationError: If required parameters are missing or invalid
        HTTPException: If user lacks write access to collection
    """
    body = json.loads(event["body"])
    bucket = os.environ["BUCKET_NAME"]

    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    # Get user context
    username = get_username(event)
    user_groups = get_groups(event)
    admin = is_admin(event)

    # Ensure repository exists and user has access
    repository = get_repository(event, repository_id=repository_id)

    # Determine collection ID
    # Priority: 1. body.collectionId, 2. embedding model ID (default collection)
    collection_id = body.get("collectionId")

    if not collection_id:
        # Default to embedding model-based collection for backward compatibility
        embedding_model = body.get("embeddingModel", {})
        model_name = embedding_model.get("modelName")
        if model_name:
            collection_id = model_name
        else:
            # Fall back to repository's embedding model
            collection_id = repository.get("embeddingModelId", "")

    if not collection_id:
        raise ValidationError("collectionId is required or embeddingModel.modelName must be provided")

    # Get collection configuration and validate access
    try:
        collection = collection_service.get_collection(
            collection_id=collection_id,
            repository_id=repository_id,
            user_id=username,
            user_groups=user_groups,
            is_admin=admin,
        )
    except ValidationError as e:
        # If collection not found, check if it's a default collection (embedding model ID)
        # For backward compatibility, create a default collection on-the-fly
        if collection_id == repository.get("embeddingModelId"):
            logger.info(f"Using default collection {collection_id} for repository {repository_id}")
            # Use legacy behavior - no collection-specific settings
            collection = None
        else:
            raise ValidationError(f"Collection '{collection_id}' not found or access denied: {str(e)}")

    # Determine chunking strategy
    chunk_strategy = None

    # Check if user provided override chunking strategy
    override_chunking = body.get("chunkingStrategy")

    if collection:
        # Check if chunking override is allowed
        if override_chunking and collection.allowChunkingOverride:
            # Use provided chunking strategy
            try:
                # Parse the chunking strategy from the request
                strategy_type = override_chunking.get("type")
                if strategy_type == "FIXED" or strategy_type == "fixed":
                    chunk_strategy = FixedChunkingStrategy(**override_chunking)
                else:
                    logger.warning(
                        f"Unsupported chunking strategy type: {strategy_type}. "
                        f"Only FIXED is currently supported. Using collection default."
                    )
                    chunk_strategy = collection.chunkingStrategy
            except Exception as e:
                logger.warning(f"Failed to parse override chunking strategy: {e}, using collection default")
                chunk_strategy = collection.chunkingStrategy
        else:
            # Use collection's chunking strategy
            chunk_strategy = collection.chunkingStrategy

    # Fall back to legacy query parameters if no strategy determined
    if not chunk_strategy:
        query_string_params = event.get("queryStringParameters", {}) or {}
        chunk_size = int(query_string_params.get("chunkSize", 1000))
        chunk_overlap = int(query_string_params.get("chunkOverlap", 200))
        chunk_strategy = FixedChunkingStrategy(size=str(chunk_size), overlap=str(chunk_overlap))

    # Get metadata from collection and merge with request metadata
    metadata = {}
    if collection and collection.metadata:
        metadata = collection.metadata.model_dump() if hasattr(collection.metadata, "model_dump") else {}

    # Merge with request metadata
    request_metadata = body.get("metadata", {})
    if request_metadata:
        metadata.update(request_metadata)

    # Get embedding model from collection or repository
    embedding_model_id = None
    if collection:
        # Use collection's embedding model if specified
        embedding_model_id = collection.embeddingModel if hasattr(collection, "embeddingModel") else None
    if not embedding_model_id:
        # Fall back to repository's embedding model
        embedding_model_id = repository.get("embeddingModelId")

    # Create ingestion jobs
    ingestion_document_ids = []
    for key in body["keys"]:
        job = IngestionJob(
            repository_id=repository_id,
            collection_id=collection_id,
            chunk_strategy=chunk_strategy,
            embedding_model=embedding_model_id,
            s3_path=f"s3://{bucket}/{key}",
            username=username,
        )
        ingestion_job_repository.save(job)
        ingestion_service.create_ingest_job(job)
        ingestion_document_ids.append(job.id)

    logger.info(f"Created {len(ingestion_document_ids)} ingestion jobs for collection {collection_id}")

    # Build response with job details
    jobs = []
    for job_id in ingestion_document_ids:
        try:
            job = ingestion_job_repository.find_by_id(job_id)
            jobs.append(
                {
                    "jobId": job.id,
                    "documentId": job.document_id,
                    "status": job.status,
                    "s3Path": job.s3_path,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve job {job_id}: {e}")
            jobs.append({"jobId": job_id, "status": "UNKNOWN"})

    response = {
        "jobs": jobs,
        "collectionId": collection_id,
    }

    # Add collection name if available
    if collection:
        response["collectionName"] = collection.name or collection_id

    return response


@api_wrapper
def get_document(event: dict, context: dict) -> Dict[str, Any]:
    """Get a document by ID.

    Args:
        event (dict): The Lambda event object containing:
            path_params:
                repositoryId - the repository
                documentId - the document

    Returns:
        dict: The document object
    """
    path_params = event.get("pathParameters", {}) or {}
    repository_id = path_params.get("repositoryId")
    document_id = path_params.get("documentId")

    _ = get_repository(event, repository_id=repository_id)
    doc = doc_repo.find_by_id(document_id=document_id)

    return doc.model_dump()


@api_wrapper
def download_document(event: dict, context: dict) -> str:
    """Generate a pre-signed S3 URL for downloading a file from the RAG ingested files.
    Args:
        event (dict): The Lambda event object containing:
            path_params:
                repositoryId - the repository
                documentId - the document

    Returns:
        url: The presigned URL response object with download fields and URL

    Notes:
        - URL expires in 300 seconds (5 mins)
    """
    path_params = event.get("pathParameters", {}) or {}
    repository_id = path_params.get("repositoryId")
    document_id = path_params.get("documentId")

    _ = get_repository(event, repository_id=repository_id)
    doc = doc_repo.find_by_id(document_id=document_id)

    source = doc.source
    bucket, key = source.replace("s3://", "").split("/", 1)

    url: str = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=300,
    )

    return url


@api_wrapper
def presigned_url(event: dict, context: dict) -> dict:
    """Generate a pre-signed URL for uploading files to the RAG ingest bucket.

    Args:
        event (dict): The Lambda event object containing:
            - body: The key for the file
            - requestContext.authorizer.username: The authenticated username
        context (dict): The Lambda context object

    Returns:
        dict: A dictionary containing:
            - response: The presigned URL response object with upload fields and URL

    Notes:
        - URL expires in 3600 seconds (1 hour)
        - Maximum file size is 52428800 bytes (50MB)
    """
    response = ""
    key = event["body"]

    # Set derived values for conditions and fields
    username = get_username(event)

    # Conditions is an array of dictionaries.
    # content-length-range restricts the size of the file uploaded
    # and should match any restrictions applied in the frontend
    conditions = [{"x-amz-meta-user": username}, ["content-length-range", 0, 52428800]]

    # Fields is just a regular dictionary
    fields = {"x-amz-meta-user": username}

    response = s3.generate_presigned_post(
        Bucket=os.environ["BUCKET_NAME"],
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=3600,
    )
    return {"response": response}


@api_wrapper
def list_docs(event: dict, context: dict) -> dict[str, Any]:
    """List all documents for a given repository/collection.

    Args:
        event (dict): The Lambda event object containing query parameters
            - pathParameters.repositoryId: The repository id to list documents for
            - queryStringParameters.collectionId: The collection id to list documents for
        context (dict): The Lambda context object

    Returns:
        Dict containing documents, pagination info, and metadata

    Raises:
        KeyError: If collectionId is not provided in queryStringParameters
    """

    path_params = event.get("pathParameters", {}) or {}
    repository_id = path_params.get("repositoryId")

    query_string_params = event.get("queryStringParameters", {}) or {}
    collection_id = query_string_params.get("collectionId")
    last_evaluated: Optional[dict[str, Optional[str]]] = None

    if "lastEvaluatedKeyPk" in query_string_params:
        last_evaluated = {
            "pk": (
                urllib.parse.unquote(query_string_params["lastEvaluatedKeyPk"])
                if "lastEvaluatedKeyPk" in query_string_params
                else None
            ),
            "document_id": (
                urllib.parse.unquote(query_string_params["lastEvaluatedKeyDocumentId"])
                if "lastEvaluatedKeyDocumentId" in query_string_params
                else None
            ),
            "repository_id": (
                urllib.parse.unquote(query_string_params["lastEvaluatedKeyRepositoryId"])
                if "lastEvaluatedKeyRepositoryId" in query_string_params
                else None
            ),
        }

    # Use shared pagination utility
    page_size = PaginationParams.parse_page_size(query_string_params)

    docs, last_evaluated, total_documents = doc_repo.list_all(
        repository_id=repository_id, collection_id=collection_id, last_evaluated_key=last_evaluated, limit=page_size
    )
    return {
        "documents": [doc.model_dump() for doc in docs],
        "lastEvaluated": last_evaluated,
        "totalDocuments": total_documents,
        "hasNextPage": last_evaluated is not None,
        "hasPreviousPage": "lastEvaluated" in query_string_params,
    }


@api_wrapper
def list_jobs(event: Dict[str, Any], context: dict) -> Dict[str, Any]:
    """List ingestion jobs for a specific repository with filtering and pagination.

    Args:
        event: The Lambda event object containing path and query parameters
        context: The Lambda context object

    Returns:
        Dict[str, Any]: Response dictionary with jobs, pagination info, and metadata

    Raises:
        ValidationError: If repositoryId is not provided or parameters are invalid
    """
    # Extract and validate parameters
    params = ListJobsParams.from_event(event)

    # Validate repository access
    _ = get_repository(event, repository_id=params.repository_id)

    # Get user context
    username, is_admin_user = get_user_context(event)

    # Fetch jobs from repository
    jobs, returned_last_evaluated_key = ingestion_job_repository.list_jobs_by_repository(
        repository_id=params.repository_id,
        username=username,
        is_admin=is_admin_user,
        time_limit_hours=params.time_limit_hours,
        page_size=params.page_size,
        last_evaluated_key=params.last_evaluated_key,
    )

    # Calculate pagination state
    pagination = PaginationResult.from_keys(
        original_key=params.last_evaluated_key, returned_key=returned_last_evaluated_key
    )

    response = ListJobsResponse(
        jobs=jobs,
        lastEvaluatedKey=returned_last_evaluated_key,
        hasNextPage=pagination.has_next_page,
        hasPreviousPage=pagination.has_previous_page,
    )

    return response.model_dump()


@api_wrapper
@admin_only
def create(event: dict, context: dict) -> Any:
    """
    Create a new process execution using AWS Step Functions. This function is only accessible by administrators.

    Args:
        event (dict): The Lambda event object containing:
            - body: A JSON string with the process creation details.
        context (dict): The Lambda context object.

    Returns:
        Dict[str, str]: A dictionary containing:
            - status: Success status message.
            - executionArn: The ARN of the step function execution.

    Raises:
        ValueError: If the user is not an administrator.
    """
    # Fetch the Step Function ARN from SSM Parameter Store
    parameter_name = os.environ["LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER"]
    state_machine_arn = ssm_client.get_parameter(Name=parameter_name)

    # Deserialize the event body and prepare input for Step Functions
    input_data = json.loads(event["body"])
    serializer = TypeSerializer()

    # Start Step Function execution
    response = step_functions_client.start_execution(
        stateMachineArn=state_machine_arn["Parameter"]["Value"],
        input=json.dumps(
            {
                "body": input_data,
                "config": {key: serializer.serialize(value) for key, value in input_data["ragConfig"].items()},
            }
        ),
    )

    # Return success status and execution ARN
    return {"status": "success", "executionArn": response["executionArn"]}


@api_wrapper
def get_repository_by_id(event: dict, context: dict) -> Dict[str, Any]:
    """
    Get a vector store configuration by ID.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository ID to retrieve
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: The repository configuration with default values for new fields

    Raises:
        ValidationError: If repositoryId is missing
        HTTPException: If repository not found or access denied
    """
    # Extract path parameters
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    if not repository_id:
        raise ValidationError("repositoryId is required")

    # Get repository and check access
    repository = get_repository(event, repository_id)

    return repository


@api_wrapper
@admin_only
def update_repository(event: dict, context: dict) -> Dict[str, Any]:
    """
    Update a vector store configuration. This function is only accessible by administrators.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository ID to update
            - body: JSON with fields to update (UpdateVectorStoreRequest)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: The updated repository configuration

    Raises:
        ValidationError: If validation fails
        HTTPException: If repository not found
    """
    from models.domain_objects import UpdateVectorStoreRequest

    # Extract path parameters
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    if not repository_id:
        raise ValidationError("repositoryId is required")

    # Parse request body
    try:
        body = json.loads(event.get("body", {}))
        request = UpdateVectorStoreRequest(**body)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in request body: {e}")
    except Exception as e:
        raise ValidationError(f"Invalid request: {e}")

    # Ensure repository exists
    _ = vs_repo.find_repository_by_id(repository_id)

    # Build updates dictionary (only include fields that were provided)
    updates = {}
    if request.repositoryName is not None:
        updates["repositoryName"] = request.repositoryName
    if request.embeddingModelId is not None:
        updates["embeddingModelId"] = request.embeddingModelId
    if request.allowedGroups is not None:
        updates["allowedGroups"] = request.allowedGroups
    if request.allowUserCollections is not None:
        updates["allowUserCollections"] = request.allowUserCollections
    if request.metadata is not None:
        updates["metadata"] = (
            request.metadata.model_dump() if hasattr(request.metadata, "model_dump") else request.metadata
        )
    if request.pipelines is not None:
        updates["pipelines"] = [p.model_dump() if hasattr(p, "model_dump") else p for p in request.pipelines]

    # Update repository
    updated_config = vs_repo.update(repository_id, updates)

    return updated_config


@api_wrapper
@admin_only
def delete(event: dict, context: dict) -> Any:
    """
    Delete a vector store process using AWS Step Functions. This function ensures
    that the user is an administrator or owns the vector store being deleted.
    Also deletes all associated collections and their documents.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository id of the vector store to delete.
        context (dict): The Lambda context object.

    Returns:
        Dict[str, str]: A dictionary containing:
            - status: Success status message.
            - executionArn: The ARN of the step function execution.

    Raises:
        ValueError: If the repository is not found.
    """
    # Retrieve the repository ID from the path parameters in the event object
    path_params = event.get("pathParameters", {}) or {}
    repository_id = path_params.get("repositoryId", None)
    if not repository_id:
        raise ValidationError("repositoryId is required")

    repository = vs_repo.find_repository_by_id(repository_id=repository_id, raw_config=True)

    # Delete all collections associated with this repository
    try:
        logger.info(f"Deleting all collections for repository: {repository_id}")
        collections = collection_service.list_collections(
            repository_id=repository_id,
            user_id="admin",
            user_groups=[],
            is_admin=True,
            pagination_params=PaginationParams(page_size=1000),  # Get all collections
        )

        for collection in collections.collections:
            try:
                logger.info(f"Deleting collection: {collection.collectionId}")
                collection_service.delete_collection(
                    collection_id=collection.collectionId,
                    repository_id=repository_id,
                    user_id="admin",
                    user_groups=[],
                    is_admin=True,
                )
            except Exception as e:
                logger.error(f"Error deleting collection {collection.collectionId}: {str(e)}")
                # Continue with other collections even if one fails
    except Exception as e:
        logger.error(f"Error listing/deleting collections for repository {repository_id}: {str(e)}")
        # Continue with repository deletion even if collection cleanup fails

    if repository.get("legacy", False) is True:
        _remove_legacy(repository_id)
        vs_repo.delete(repository_id=repository_id)
        return {"status": "success", "executionArn": "legacy"}
    else:
        # Fetch the ARN of the State Machine for deletion from the SSM Parameter Store
        parameter_name = os.environ["LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER"]
        state_machine_arn = ssm_client.get_parameter(Name=parameter_name)

        # Start the execution of the State Machine to delete the vector store
        response = step_functions_client.start_execution(
            stateMachineArn=state_machine_arn["Parameter"]["Value"],
            input=json.dumps({"repositoryId": repository_id, "stackName": repository.get("stackName")}),
        )

        # Return success status and execution ARN
        return {"status": "success", "executionArn": response["executionArn"]}


@api_wrapper
@admin_only
def delete_index(event: dict, context: dict) -> None:
    """
    Clear the vector store for the specified repository and model.

    Args:
        event (dict): The Lambda event object containing path parameters
        context (dict): The Lambda context object
    """
    path_params = event.get("pathParameters", {}) or {}
    repository_id = path_params.get("repositoryId", None)
    if not repository_id:
        raise ValidationError("repositoryId is required")
    collection_id = path_params.get("collectionId", None)
    if not collection_id:
        raise ValidationError("collectionId is required")

    repository = vs_repo.find_repository_by_id(repository_id=repository_id)
    id_token = get_id_token(event)
    embeddings = RagEmbeddings(model_name=collection_id, id_token=id_token)  # model_name can be anything
    vs = get_vector_store_client(repository_id, index=collection_id, embeddings=embeddings)

    try:
        if RepositoryType.is_type(repository, RepositoryType.OPENSEARCH):
            if vs.client.indices.exists(index=collection_id):
                vs.client.indices.delete(index=collection_id)
                logger.info(f"Deleted OpenSearch index: {collection_id}")
            else:
                logger.info(f"OpenSearch index {collection_id} does not exist")
        elif RepositoryType.is_type(repository, RepositoryType.PGVECTOR):
            # For PGVector, delete all documents in the collection
            vs.delete_collection()
            logger.info(f"Deleted PGVector collection: {collection_id}")
        else:
            logger.error(f"Unsupported repository type: {repository.get('type')}")
            return {"status": "error", "message": "Repository is not supported"}
    except Exception as e:
        logger.error(f"Failed to clear vector store: {e}")
        return {"status": "error", "message": str(e)}


def _remove_legacy(repository_id: str) -> None:
    registered_repositories = ssm_client.get_parameter(Name=os.environ["REGISTERED_REPOSITORIES_PS"])
    registered_repositories = json.loads(registered_repositories["Parameter"]["Value"])
    updated_repositories = [repo for repo in registered_repositories if repo.get("repositoryId") != repository_id]

    if len(updated_repositories) < len(registered_repositories):
        # Save the updated list back to the parameter store
        ssm_client.put_parameter(
            Name=os.environ["REGISTERED_REPOSITORIES_PS"],
            Value=json.dumps(updated_repositories),
            Type="String",
            Overwrite=True,
        )


def _similarity_search(vs, query: str, top_k: int) -> list[dict[str, Any]]:
    """Perform similarity search without scores.

    Args:
        vs: Vector store instance
        query: Search query string
        top_k: Number of top results to return

    Returns:
        List of documents with page_content and metadata
    """
    results = vs.similarity_search_with_score(
        query,
        k=top_k,
    )

    return [{"page_content": doc.page_content, "metadata": doc.metadata} for doc, score in results]


def _similarity_search_with_score(vs, query: str, top_k: int, repository: dict) -> list[dict[str, Any]]:
    """Perform similarity search with normalized scores.

    Args:
        vs: Vector store instance
        query: Search query string
        top_k: Number of top results to return
        repository: Repository configuration dict

    Returns:
        List of documents with page_content, metadata, and similarity_score
    """
    results = vs.similarity_search_with_score(
        query,
        k=top_k,
    )
    docs = []
    for i, (doc, score) in enumerate(results):
        similarity_score = RepositoryType.get_type(repository=repository).calculate_similarity_score(score)
        logger.info(
            f"Result {i + 1}: Raw Score={score:.4f}, Similarity={similarity_score:.4f}, "
            + f"Content: {doc.page_content[:200]}..."
        )
        logger.info(f"Result {i + 1} metadata: {doc.metadata}")
        docs.append(
            {
                "page_content": doc.page_content,
                "metadata": {**doc.metadata, "similarity_score": similarity_score},
            }
        )

    if results and max(score for _, score in results) < 0.3:
        logger.warning(f"All similarity < 0.3 for query '{query}' - possible embedding model mismatch")

    return docs
