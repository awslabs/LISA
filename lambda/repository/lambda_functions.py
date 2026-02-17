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
from types import SimpleNamespace
from typing import Any, cast

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.config import Config
from models.domain_objects import (
    FilterParams,
    IngestDocumentRequest,
    IngestionJob,
    IngestionStatus,
    IngestionType,
    ListJobsResponse,
    PaginationParams,
    PaginationResult,
    RagCollectionConfig,
    RagDocument,
    SortParams,
    UpdateVectorStoreRequest,
    VectorStoreConfig,
    VectorStoreStatus,
)
from repository.collection_service import CollectionService
from repository.config.params import ListJobsParams
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.metadata_generator import MetadataGenerator
from repository.rag_document_repo import RagDocumentRepository
from repository.s3_metadata_manager import S3MetadataManager
from repository.services import RepositoryServiceFactory
from repository.vector_store_repo import VectorStoreRepository
from utilities.auth import admin_only, get_groups, get_user_context, get_username, is_admin, user_has_group_access
from utilities.bedrock_kb import create_s3_scan_job
from utilities.bedrock_kb_discovery import (
    build_pipeline_configs_from_kb_config,
    get_available_data_sources,
    list_knowledge_bases,
)
from utilities.bedrock_kb_validation import validate_bedrock_kb_exists
from utilities.common_functions import api_wrapper, retry_config
from utilities.exceptions import ForbiddenException, NotFoundException
from utilities.repository_types import RepositoryType
from utilities.validation import ValidationError

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
collection_service = CollectionService(vector_store_repo=vs_repo, document_repo=doc_repo)


@api_wrapper
def list_all(event: dict, context: dict) -> list[dict[str, Any]]:
    """
    List all available repositories that the user has access to.

    Args:
        event: Lambda event containing user authentication
        context: Lambda context

    Returns:
        List of repository configurations user can access
    """
    _, is_admin, groups = get_user_context(event)
    registered_repositories = vs_repo.get_registered_repositories()
    return [
        repo
        for repo in registered_repositories
        if is_admin or user_has_group_access(groups, repo.get("allowedGroups", []))
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
def similarity_search(event: dict, context: dict) -> dict[str, Any]:
    """Return documents matching the query.

    Conducts similarity search against the vector store returning the top K
    documents based on the specified query.

    Args:
        event (dict): The Lambda event object containing:
            - queryStringParameters.modelName (optional): Name of the embedding model
              (not needed if collectionId provided)
            - queryStringParameters.collectionName (optional): Collection ID to search within. Will override
                any modelName.
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
    query_string_params = event.get("queryStringParameters")
    path_params = event.get("pathParameters")
    query = query_string_params.get("query")  # type: ignore[union-attr]
    top_k = int(query_string_params.get("topK", 3))  # type: ignore[union-attr]
    include_score = query_string_params.get("score", "false").lower() == "true"  # type: ignore[union-attr]
    repository_id = path_params.get("repositoryId")  # type: ignore[union-attr]
    collection_id = query_string_params.get("collectionId")  # type: ignore[union-attr]

    repository = get_repository(event, repository_id=repository_id)

    # Get user context for collection access
    username, is_admin, groups = get_user_context(event)

    is_default = collection_id is not None and collection_id == repository.get("embeddingModelId")
    # Determine embedding model
    model_name = (
        collection_service.get_collection_model(
            repository_id=repository_id,
            collection_id=collection_id if not is_default else None,  # type: ignore[arg-type]
            username=username,
            user_groups=groups,
            is_admin=is_admin,
        )
        if collection_id
        else query_string_params.get("modelName")  # type: ignore[union-attr]
    )

    if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
        # No collectionId will query the entire Knowledge base. Reserve for Admins.
        if collection_id is None and not is_admin:
            raise ValidationError("collectionId is required when searching Bedrock Knowledge Bases")
    elif not model_name:
        raise ValidationError("modelName is required when collectionId is not provided")

    # Use repository service for similarity search
    service = RepositoryServiceFactory.create_service(repository)

    # Use collection_id as vector store index if provided, otherwise use model_name
    search_collection_id = collection_id or model_name
    logger.info(f"Searching in collection: {search_collection_id} with embedding model: {model_name}")

    # Delegate to service for retrieval - service handles repository-specific logic
    docs = service.retrieve_documents(
        query=query,
        collection_id=search_collection_id,  # type: ignore[arg-type]
        top_k=top_k,
        model_name=model_name,  # type: ignore[arg-type]
        include_score=include_score,
        bedrock_agent_client=bedrock_client,
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


def get_repository(event: dict[str, Any], repository_id: str) -> dict[str, Any]:
    """Ensures a user has access to the repository or else raises an HTTPException."""
    repo: dict[str, Any] = vs_repo.find_repository_by_id(repository_id)

    # Admins have access to all repositories
    if is_admin(event):
        return repo

    # Non-admins must have matching group access
    user_groups = get_groups(event)
    if not user_has_group_access(user_groups, repo.get("allowedGroups", [])):
        raise ForbiddenException("User does not have permission to access this repository")

    return repo


def create_bedrock_collection(event: dict, context: dict) -> dict[str, Any]:
    """
    Create collections for a Bedrock Knowledge Base repository based on pipeline configurations.
    This is called by the state machine during repository creation.

    Each pipeline configuration represents a data source and should have a corresponding collection.

    Args:
        event (dict): The Lambda event object containing:
            - ragConfig: Repository configuration with repositoryId and pipelines
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing:
            - collections: List of created collection configurations
            - count: Number of collections created

    Raises:
        ValidationError: If validation fails
        HTTPException: If repository not found
    """
    try:
        # Extract repository config from state machine input
        rag_config = event.get("ragConfig", {})
        repository_id = rag_config.get("repositoryId")

        if not repository_id:
            raise ValidationError("repositoryId is required in ragConfig")

        logger.info(f"Creating collection(s) for Bedrock KB repository: {repository_id}")

        # Get repository configuration
        repository = vs_repo.find_repository_by_id(repository_id=repository_id)

        # Get pipeline configurations - each pipeline should have a collectionId
        pipelines = repository.get("pipelines", [])

        if not pipelines:
            raise ValidationError(f"No pipelines found in Bedrock KB repository {repository_id}")

        logger.info(f"Found {len(pipelines)} pipeline(s) to create collections for")

        # Use repository service to create collections
        service = RepositoryServiceFactory.create_service(repository)

        # Create a collection for each pipeline (skip if already exists)
        created_collections = []
        skipped_collections = []
        for pipeline in pipelines:
            collection_id = pipeline.get("collectionId")
            if not collection_id:
                logger.warning(f"Pipeline missing collectionId, skipping: {pipeline}")
                continue

            collection_name = pipeline.get("collectionName", collection_id)
            s3_bucket = pipeline.get("s3Bucket", "")
            s3_prefix = pipeline.get("s3Prefix", "")
            s3_uri = f"s3://{s3_bucket}/{s3_prefix}" if s3_bucket else ""

            # Check if collection already exists
            try:
                existing_collection = collection_service.get_collection(
                    repository_id=repository_id,
                    collection_id=collection_id,
                    username="system",
                    user_groups=[],
                    is_admin=True,
                )
                if existing_collection:
                    logger.info(f"Collection {collection_id} already exists, skipping creation")
                    skipped_collections.append(existing_collection.model_dump(mode="json"))
                    continue
            except (NotFoundException, ValidationError):
                # Collection doesn't exist, proceed with creation
                pass

            logger.info(
                f"Creating collection for pipeline with collectionId={collection_id}, "
                f"collectionName={collection_name}, s3Uri={s3_uri}"
            )

            # Create collection using service helper
            collection = service._create_collection_for_data_source(  # type: ignore[attr-defined]
                data_source_id=collection_id, s3_uri=s3_uri, is_default=False, collection_name=collection_name
            )

            # Save the collection
            collection_service.create_collection(collection=collection, username="system")
            logger.info(f"Successfully saved collection: {collection.collectionId}")
            created_collections.append(collection.model_dump(mode="json"))

            # Create S3 scan job to ingest existing documents
            if s3_bucket:
                logger.info(f"Creating S3 scan job for bucket {s3_bucket} with prefix '{s3_prefix}'")

                # Merge metadata from repository and collection for the scan job
                merged_metadata = MetadataGenerator.merge_metadata(
                    repository=repository,
                    collection=collection.model_dump(),
                    document_metadata=None,
                    for_bedrock_kb=False,  # Keep tags as array for ingestion jobs
                )

                job_id = create_s3_scan_job(
                    ingestion_job_repository=ingestion_job_repository,
                    ingestion_service=ingestion_service,
                    repository_id=repository_id,
                    collection_id=collection_id,
                    embedding_model=collection.embeddingModel,
                    s3_bucket=s3_bucket,
                    s3_prefix=s3_prefix,
                    metadata=merged_metadata,
                )
                logger.info(f"Created S3 scan job {job_id} for collection {collection_id}")

        if not created_collections and not skipped_collections:
            raise ValidationError(f"Failed to create any collections for repository {repository_id}")

        # Return all created and skipped collections
        all_collections = created_collections + skipped_collections
        result: dict[str, Any] = {
            "collections": all_collections,
            "count": len(all_collections),
            "created": len(created_collections),
            "skipped": len(skipped_collections),
        }
        logger.info(f"Collection summary: {len(created_collections)} created, {len(skipped_collections)} skipped")
        logger.info(f"Successfully created {len(created_collections)} collection(s) for repository {repository_id}")
        return result

    except Exception as e:
        logger.error(f"Error creating Bedrock collection(s): {str(e)}")
        raise


@api_wrapper
@admin_only
def create_collection(event: dict, context: dict) -> dict[str, Any]:
    """
    Create a new collection within a vector store.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - body: JSON with collection configuration (RagCollectionConfig)
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

    # Get user context
    username, _, _ = get_user_context(event)

    # Ensure repository exists and user has access
    repository = get_repository(event, repository_id=repository_id)

    # Block user-created collections for Bedrock Knowledge Base repositories
    if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
        raise ValidationError(
            "Bedrock Knowledge Base repositories do not support user created collections. "
            "Update the repository to add a new datasource collection."
        )

    # Parse request body
    try:
        body = json.loads(event.get("body", {}))
        # Add required fields
        body["repositoryId"] = repository_id
        body["createdBy"] = username
        collection = RagCollectionConfig(**body)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in request body: {e}")
    except Exception as e:
        raise ValidationError(f"Invalid request: {e}")

    # Validate embedding model - either collection must have one or repository must have a default
    if not collection.embeddingModel and not repository.get("embeddingModelId"):
        raise ValidationError(
            "Either the collection must specify an embeddingModel or "
            "the repository must have a default embeddingModelId"
        )

    # Create collection via service
    created_collection = collection_service.create_collection(
        collection=collection,
        username=username,
    )

    # Initialize backing storage (e.g., PGVector table) for the new collection
    embedding_model = collection.embeddingModel or repository.get("embeddingModelId")
    service = RepositoryServiceFactory.create_service(repository)
    service.initialize_collection(
        collection_id=created_collection.collectionId,
        embedding_model=embedding_model,
    )

    # Return collection configuration
    result: dict[str, Any] = created_collection.model_dump(mode="json")
    return result


@api_wrapper
def get_collection(event: dict, context: dict) -> dict[str, Any]:
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
    username, is_admin, groups = get_user_context(event)

    # Ensure repository exists and user has access
    repo = get_repository(event, repository_id=repository_id)

    if repo.get("embeddingModelId") == collection_id:
        # Not a real collection - create virtual default collection
        service = RepositoryServiceFactory.create_service(repo)
        collection = service.create_default_collection()
    else:
        # Get collection via service (includes access control check)
        collection = collection_service.get_collection(
            repository_id=repository_id,
            collection_id=collection_id,
            username=username,
            user_groups=groups,
            is_admin=is_admin,
        )

    if collection is None:
        raise NotFoundException(f"Collection '{collection_id}' not found in repository '{repository_id}'")

    # Return collection configuration
    result: dict[str, Any] = collection.model_dump(mode="json")
    return result


@api_wrapper
@admin_only
def update_collection(event: dict, context: dict) -> dict[str, Any]:
    """
    Update a collection within a vector store.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - pathParameters.collectionId: The collection ID
            - body: JSON with partial collection updates (RagCollectionConfig)
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

    # Get user context
    username, is_admin, groups = get_user_context(event)

    # Ensure repository exists and user has access
    _ = get_repository(event, repository_id=repository_id)

    # Parse request body - accept partial updates as a dictionary
    try:
        body = json.loads(event.get("body", {}))
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in request body: {e}")

    # Create a simple namespace object to hold the update fields
    # The service layer expects an object with attributes, not a dict
    request = SimpleNamespace(**body)

    # Update collection via service (includes access control check)
    updated_collection = collection_service.update_collection(
        collection_id=collection_id,
        repository_id=repository_id,
        collection_data=request,
        username=username,
        user_groups=groups,
        is_admin=is_admin,
    )

    result: dict[str, Any] = updated_collection.model_dump(mode="json")
    return result


@api_wrapper
@admin_only
def delete_collection(event: dict, context: dict) -> dict[str, Any]:
    """
    Delete a collection (regular or default) within a vector store.

    Path: /repository/{repositoryId}/collection/{collectionId}

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The parent repository ID
            - pathParameters.collectionId: The collection ID (optional for default collections)
            - queryStringParameters.embeddingName: Embedding model name (for default collections)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: Dictionary with deletion type and job ID

    Raises:
        ValidationError: If validation fails or user lacks permission
        HTTPException: If repository or collection not found or access denied
    """
    # Extract parameters
    path_params = event.get("pathParameters", {})
    query_params = event.get("queryStringParameters", {}) or {}

    repository_id = path_params.get("repositoryId")
    collection_id = path_params.get("collectionId")  # May be None for default collections
    embedding_name = query_params.get("embeddingName")  # For default collections

    if not repository_id:
        raise ValidationError("repositoryId is required")

    # Validate that we have either collectionId or embeddingName
    if not collection_id and not embedding_name:
        raise ValidationError("Either collectionId or embeddingName must be provided")

    # Get user context
    username, is_admin, groups = get_user_context(event)

    # Ensure repository exists and user has access
    repo = get_repository(event, repository_id=repository_id)

    is_default_collection = repo.get("embeddingModelId") == collection_id
    # Delete collection via service
    result: dict[str, Any] = collection_service.delete_collection(
        repository_id=repository_id,
        collection_id=collection_id,  # None for default collections
        embedding_name=embedding_name if is_default_collection else None,  # None for regular collections
        username=username,
        user_groups=groups,
        is_admin=is_admin,
    )

    return result


@api_wrapper
def list_collections(event: dict, context: dict) -> dict[str, Any]:
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
    username, is_admin, groups = get_user_context(event)

    # Ensure repository exists and user has access
    _ = get_repository(event, repository_id=repository_id)

    # Parse query parameters
    query_params = event.get("queryStringParameters", {}) or {}

    # Parse pagination parameters using PaginationParams composition object
    page_size = PaginationParams.parse_page_size(query_params, default=20, max_size=100)

    # Define key fields based on the potential DynamoDB indexes being used
    # collectionId is always present, status and createdAt are optional depending on the index
    key_fields = ["collectionId", "status", "createdAt"]
    last_evaluated_key = PaginationParams.parse_last_evaluated_key(query_params, key_fields)

    # Parse filter parameters using FilterParams composition object
    filter_params = FilterParams.from_query_params(query_params)
    filter_text = filter_params.filter_text
    status_filter = filter_params.status_filter

    # Parse sort parameters using SortParams composition object
    # sort_params = SortParams.from_query_params(query_params)
    # sort_by = sort_params.sort_by
    # sort_order = sort_params.sort_order

    # List collections via service (includes access control filtering)
    collections, next_key = collection_service.list_collections(
        repository_id=repository_id,
        username=username,
        user_groups=groups,
        is_admin=is_admin,
        page_size=page_size,
        last_evaluated_key=last_evaluated_key,
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
            total_count = collection_service.count_collections(repository_id=repository_id)

            # Calculate page numbers if we have total count
            if total_count is not None:
                total_pages = (total_count + page_size - 1) // page_size
                # Estimate current page based on whether we have a last_evaluated_key
                current_page = 1 if not last_evaluated_key else None
        except Exception as e:
            logger.warning(f"Failed to get total count for repository {repository_id}: {e}")

    # Build response
    response = {
        "collections": [c.model_dump(mode="json") for c in collections if c is not None],
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


@api_wrapper
def list_user_collections(event: dict, context: dict) -> dict[str, Any]:
    """
    List all collections user has access to across all repositories.

    Args:
        event (dict): The Lambda event object containing:
            - queryStringParameters.pageSize: Items per page (optional, default: 20, max: 100)
            - queryStringParameters.filter: Text filter for name/description (optional)
            - queryStringParameters.sortBy: Sort field (name, createdAt, updatedAt) (optional, default: createdAt)
            - queryStringParameters.sortOrder: Sort order (asc, desc) (optional, default: desc)
            - queryStringParameters.lastEvaluatedKey: Pagination token (optional, JSON string)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: A dictionary containing:
            - collections: List of collection configurations with repositoryName
            - pagination: Pagination metadata
            - lastEvaluatedKey: Pagination token for next page
            - hasNextPage: Whether there are more pages
            - hasPreviousPage: Whether there is a previous page

    Raises:
        ValidationError: If validation fails
        HTTPException: If authentication fails
    """
    # Get user context
    username, is_admin, groups = get_user_context(event)
    logger.info(f"list_user_collections called by user={username}, is_admin={is_admin}")

    # Parse query parameters
    query_params = event.get("queryStringParameters", {}) or {}

    # Parse pagination parameters
    page_size = PaginationParams.parse_page_size(query_params, default=20, max_size=100)

    # Parse pagination token
    pagination_token = None
    if "lastEvaluatedKey" in query_params:
        try:
            pagination_token = json.loads(query_params["lastEvaluatedKey"])
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse pagination token: {e}")
            # Continue without token (start from beginning)

    # Parse filter parameters
    filter_params = FilterParams.from_query_params(query_params)
    filter_text = filter_params.filter_text

    # Parse sort parameters
    sort_params = SortParams.from_query_params(query_params)

    # List collections via service
    collections, next_token = collection_service.list_all_user_collections(
        username=username,
        user_groups=groups,
        is_admin=is_admin,
        page_size=page_size,
        pagination_token=pagination_token,
        filter_text=filter_text,
        sort_params=sort_params,
    )

    # Calculate pagination metadata
    has_next_page = next_token is not None
    has_previous_page = pagination_token is not None

    # Encode next token as JSON string if present
    encoded_next_token = None
    if next_token:
        try:
            encoded_next_token = json.dumps(next_token)
        except Exception as e:
            logger.error(f"Failed to encode pagination token: {e}")

    # Build response
    response = {
        "collections": collections,
        "pagination": {
            "totalCount": None,  # Not calculated for cross-repository queries
            "currentPage": None,
            "totalPages": None,
        },
        "lastEvaluatedKey": encoded_next_token,
        "hasNextPage": has_next_page,
        "hasPreviousPage": has_previous_page,
    }

    logger.info(f"Returning {len(collections)} collections, hasNextPage={has_next_page}")
    return response


def _ensure_document_ownership(event: dict[str, Any], docs: list[RagDocument]) -> None:
    """Verify ownership of documents"""
    username = get_username(event)
    if is_admin(event) is False:
        for doc in docs:
            if not (doc.username == username):
                raise ValueError(f"Document {doc.document_id} is not owned by {username}")


@api_wrapper
def delete_documents(event: dict, context: dict) -> dict[str, Any]:
    """Purge all records related to the specified document from the RAG repository. If a documentId is supplied, a
    single document will be removed. If a documentName is supplied, all documents with that name will be removed

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository id of VectorStore
            - queryStringParameters.collectionId: The collection ID
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
    if not repository_id:
        raise ValidationError("repositoryId is required")

    # Ensure repo access
    _ = get_repository(event, repository_id=repository_id)

    rag_documents: list[RagDocument] = []
    if document_ids:
        rag_documents = [
            doc
            for doc in (
                doc_repo.find_by_id(document_id=document_id)
                for document_id in document_ids  # type: ignore[arg-type,unused-ignore]
            )
            if doc is not None
        ]

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
                embedding_model=rag_document.collection_id,  # Not needed for deletion
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


def handle_deprecated_chunking_strategy(request: IngestDocumentRequest, query_params: dict) -> None:
    """Handle deprecated chunkSize and chunkOverlap query parameters.

    This function provides backward compatibility by migrating legacy query parameters
    to the new chunkingStrategy format. It logs deprecation warnings to encourage
    migration to the new API format.

    Args:
        request: The IngestDocumentRequest object to potentially modify
        query_params: Query string parameters from the HTTP request

    Side Effects:
        - Logs deprecation warning if legacy parameters are detected
        - Modifies request.chunkingStrategy if legacy parameters are present
          and chunkingStrategy is not already set

    Deprecated Parameters:
        - chunkSize: Size of each chunk (use chunkingStrategy.size instead)
        - chunkOverlap: Overlap between chunks (use chunkingStrategy.overlap instead)
    """
    if "chunkSize" in query_params or "chunkOverlap" in query_params:
        logger.warning(
            "DEPRECATION WARNING: Query parameters 'chunkSize' and 'chunkOverlap' are deprecated. "
            "Please use the 'chunkingStrategy' object in the request body instead. "
            "Legacy parameters will be removed in a future version."
        )

        # Migrate legacy parameters to new format if chunkingStrategy not provided
        if not request.chunkingStrategy:
            chunk_size = int(query_params.get("chunkSize", 512))
            chunk_overlap = int(query_params.get("chunkOverlap", 51))

            # Create chunkingStrategy from legacy parameters
            request.chunkingStrategy = {"type": "fixed", "size": chunk_size, "overlap": chunk_overlap}
            logger.info(
                f"Migrated legacy parameters to chunkingStrategy: " f"size={chunk_size}, overlap={chunk_overlap}"
            )
        if "collectionId" in query_params:
            request.collectionId = query_params.get("collectionId")


@api_wrapper
def ingest_documents(event: dict, context: dict) -> dict:
    """Ingest documents into the RAG repository."""
    body = json.loads(event["body"])
    request = IngestDocumentRequest(**body)
    repository_id = event.get("pathParameters", {}).get("repositoryId")
    query_params = event.get("queryStringParameters", {}) or {}
    bucket = os.environ["BUCKET_NAME"]

    # Handle deprecated chunking parameters
    handle_deprecated_chunking_strategy(request, query_params)

    username, is_admin, groups = get_user_context(event)
    repository = get_repository(event, repository_id=repository_id)

    # Get collection if specified
    collection: dict[str, Any] | None = None
    if request.collectionId and request.collectionId != repository.get("embeddingModelId"):
        collection = collection_service.get_collection(
            collection_id=request.collectionId,
            repository_id=repository_id,
            username=username,
            user_groups=groups,
            is_admin=is_admin,
        ).model_dump()

    # For Bedrock KB repositories, upload metadata files BEFORE documents
    is_bedrock_kb = RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB)
    s3_metadata_manager = S3MetadataManager()

    # Create jobs
    jobs = []
    for key in request.keys:
        job = ingestion_service.create_ingestion_job(
            repository=repository,
            collection=collection,
            request=request,
            query_params=query_params,
            s3_path=f"s3://{bucket}/{key}",
            username=username,
            metadata=request.metadata,
            ingestion_type=IngestionType.MANUAL,
        )
        ingestion_job_repository.save(job)
        if is_bedrock_kb:
            # Upload metadata file
            try:
                s3_metadata_manager.upload_metadata_file(
                    s3_client=s3,
                    bucket=bucket,
                    document_key=key,
                    metadata_content=job.metadata,  # type: ignore[arg-type]
                )
                logger.info(f"Uploaded metadata file for {key}")
            except Exception as e:
                logger.error(f"Failed to upload metadata file for {key}: {e}")
        ingestion_service.submit_create_job(job)
        jobs.append({"jobId": job.id, "documentId": job.document_id, "status": job.status, "s3Path": job.s3_path})

    collection_id = job.collection_id
    collection_name: str | None = None
    if collection:
        collection_name = collection.get("name")
    if not collection_name:
        collection_name = collection_id
    result: dict[str, Any] = {"jobs": jobs, "collectionId": collection_id, "collectionName": collection_name}
    return result


@api_wrapper
def get_document(event: dict, context: dict) -> dict[str, Any]:
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
    if repository_id is None or document_id is None:
        raise ValidationError("Must set the repositoryId and documentId")
    if not isinstance(repository_id, str):
        raise ValidationError("repositoryId must be a string")
    _ = get_repository(event, repository_id=repository_id)
    doc = doc_repo.find_by_id(document_id=document_id)

    result: dict[str, Any] = doc.model_dump()  # type: ignore[union-attr]
    return result


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

    if not repository_id:
        raise ValidationError("repositoryId is required")
    _ = get_repository(event, repository_id=repository_id)
    doc = doc_repo.find_by_id(document_id=document_id)  # type: ignore[arg-type]

    source = doc.source  # type: ignore[union-attr]
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
            - queryStringParameters.collectionName: The collection name to list documents for
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

    last_evaluated: dict[str, str | None] | None = None

    if not repository_id:
        raise ValidationError("repositoryId is required")
    # Validate repository access
    _ = get_repository(event, repository_id=repository_id)

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
def list_jobs(event: dict[str, Any], context: dict) -> dict[str, Any]:
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

    if not params.repository_id:
        raise ValidationError("repositoryId is required")
    # Validate repository access
    _ = get_repository(event, repository_id=params.repository_id)

    # Get user context
    username, is_admin_user, _ = get_user_context(event)

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

    result: dict[str, Any] = response.model_dump()
    return result


@api_wrapper
@admin_only
def create(event: dict, context: dict) -> Any:
    """
    Create a new process execution using AWS Step Functions. This function is only accessible by administrators.

    For Bedrock Knowledge Base repositories, automatically adds a default pipeline configuration
    if none is provided, using the datasource S3 bucket for event-driven ingestion.

    Args:
        event (dict): The Lambda event object containing:
            - body: A JSON string with the process creation details containing VectorStoreConfig.
        context (dict): The Lambda context object.

    Returns:
        Dict[str, str]: A dictionary containing:
            - status: Success status message.
            - executionArn: The ARN of the step function execution.

    Raises:
        ValueError: If the user is not an administrator.
        ValidationError: If the request body is invalid.
    """
    # Fetch the Step Function ARN from SSM Parameter Store
    parameter_name = os.environ["LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER"]
    state_machine_arn = ssm_client.get_parameter(Name=parameter_name)

    # Get user context
    username, _, _ = get_user_context(event)

    # Deserialize the event body and parse as VectorStoreConfig
    try:
        body = json.loads(event["body"])
        # Add required fields
        body["createdBy"] = username
        vector_store_config = VectorStoreConfig(**body)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in request body: {e}")
    except Exception as e:
        raise ValidationError(f"Invalid VectorStoreConfig: {e}")

    # Auto-convert Bedrock KB config to pipelines
    if vector_store_config.type == RepositoryType.BEDROCK_KB:
        if not vector_store_config.bedrockKnowledgeBaseConfig:
            raise ValidationError("Bedrock Knowledge Base configuration is required")

        if (
            not vector_store_config.bedrockKnowledgeBaseConfig.dataSources
            or len(vector_store_config.bedrockKnowledgeBaseConfig.dataSources) == 0
        ):
            raise ValidationError(
                "Bedrock Knowledge Base repositories require at least one data source. "
                "Please select at least one data source."
            )
        # Convert bedrockKnowledgeBaseConfig to pipelines
        vector_store_config.pipelines = build_pipeline_configs_from_kb_config(  # type: ignore[assignment]
            vector_store_config.bedrockKnowledgeBaseConfig
        )

    # Convert to dictionary for Step Functions input
    rag_config = vector_store_config.model_dump(mode="json", exclude_none=True)
    input_data = {"ragConfig": rag_config}

    serializer = TypeSerializer()

    # Start Step Function execution
    response = step_functions_client.start_execution(
        stateMachineArn=state_machine_arn["Parameter"]["Value"],
        input=json.dumps(
            {
                "body": input_data,
                "config": {key: serializer.serialize(value) for key, value in rag_config.items()},
            }
        ),
    )

    # Return success status and execution ARN
    return {"status": "success", "executionArn": response["executionArn"]}


@api_wrapper
def get_repository_by_id(event: dict, context: dict) -> dict[str, Any]:
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
    repository: dict[str, Any] = get_repository(event, repository_id)

    return repository


def _get_pipeline_key(pipeline: dict) -> str:
    """Generate a unique key for a pipeline based on immutable fields."""
    collection_id = pipeline.get("collectionId", "")
    s3_bucket = pipeline.get("s3Bucket", "")
    s3_prefix = pipeline.get("s3Prefix", "")
    return f"{collection_id}:{s3_bucket}:{s3_prefix}"


def _validate_immutable_pipeline_fields(current_pipelines: list, new_pipelines: list) -> None:
    """
    Validate that immutable pipeline fields haven't changed for existing pipelines.

    Immutable fields: autoRemove, collectionId, s3Bucket, s3Prefix, trigger

    Args:
        current_pipelines: Current pipeline configurations
        new_pipelines: New pipeline configurations

    Raises:
        ValidationError: If any immutable field has changed for an existing pipeline
    """
    # If we have the same number of pipelines, check for field changes by position
    # This handles the case where immutable fields are changed (which would change the key)
    if len(current_pipelines) == len(new_pipelines):
        for _i, (current_pipeline, new_pipeline) in enumerate(zip(current_pipelines, new_pipelines)):
            # Define immutable fields
            immutable_fields = ["autoRemove", "collectionId", "s3Bucket", "s3Prefix", "trigger"]

            for field in immutable_fields:
                current_value = current_pipeline.get(field)
                new_value = new_pipeline.get(field)

                if current_value != new_value:
                    raise ValidationError(
                        f"Pipeline field '{field}' cannot be modified for existing pipelines. "
                        f"Current value: '{current_value}', attempted value: '{new_value}'. "
                        f"This field requires infrastructure redeployment. Please create a new pipeline instead."
                    )

    # Also check by key for pipelines that haven't changed position
    current_by_key = {_get_pipeline_key(p): p for p in current_pipelines}
    new_by_key = {_get_pipeline_key(p): p for p in new_pipelines}

    # Check existing pipelines for immutable field changes (for pipelines that kept the same key)
    for key, current_pipeline in current_by_key.items():
        if key in new_by_key:
            new_pipeline = new_by_key[key]

            # Define immutable fields
            immutable_fields = ["autoRemove", "collectionId", "s3Bucket", "s3Prefix", "trigger"]

            for field in immutable_fields:
                current_value = current_pipeline.get(field)
                new_value = new_pipeline.get(field)

                if current_value != new_value:
                    raise ValidationError(
                        f"Pipeline field '{field}' cannot be modified for existing pipelines. "
                        f"Current value: '{current_value}', attempted value: '{new_value}'. "
                        f"This field requires infrastructure redeployment. Please create a new pipeline instead."
                    )


@api_wrapper
@admin_only
def update_repository(event: dict, context: dict) -> dict[str, Any]:
    """
    Update a vector store configuration. This function is only accessible by administrators.

    If the pipeline configuration has changed, this will trigger an infrastructure deployment
    using the state machine, similar to repository creation.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository ID to update
            - body: JSON with fields to update (UpdateVectorStoreRequest)
        context (dict): The Lambda context object

    Returns:
        Dict[str, Any]: The updated repository configuration with executionArn if deployment triggered

    Raises:
        ValidationError: If validation fails
        HTTPException: If repository not found
    """
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

    # Get current repository configuration to check for pipeline changes
    current_repo = vs_repo.find_repository_by_id(repository_id, raw_config=True)
    current_config = current_repo.get("config", {})
    current_pipelines = current_config.get("pipelines")

    # Build updates dictionary (only include fields that were provided)
    updates = request.model_dump(exclude_none=True, mode="json")

    # Convert bedrockKnowledgeBaseConfig to pipelines for Bedrock KB repositories
    repository_type = current_config.get("type")
    if (
        repository_type == RepositoryType.BEDROCK_KB
        and hasattr(request, "bedrockKnowledgeBaseConfig")
        and request.bedrockKnowledgeBaseConfig is not None
    ):
        # Validate at least one data source
        if (
            not request.bedrockKnowledgeBaseConfig.dataSources
            or len(request.bedrockKnowledgeBaseConfig.dataSources) == 0
        ):
            raise ValidationError(
                "Bedrock Knowledge Base repositories require at least one collection. "
                "Please select at least one data source."
            )
        # Convert bedrockKnowledgeBaseConfig to pipelines
        new_pipelines = build_pipeline_configs_from_kb_config(request.bedrockKnowledgeBaseConfig)

        # Preserve existing pipeline metadata (tags, etc.) when updating Bedrock KB repositories
        if current_pipelines:
            # Create a mapping of existing pipeline metadata by collectionId
            existing_metadata = {
                pipeline.get("collectionId"): pipeline.get("metadata", {})
                for pipeline in current_pipelines
                if pipeline.get("collectionId")
            }

            # Merge existing metadata into new pipeline configurations
            for pipeline in new_pipelines:
                collection_id = pipeline.get("collectionId")
                if collection_id and collection_id in existing_metadata:
                    # Preserve existing metadata for this collection
                    pipeline["metadata"] = existing_metadata[collection_id]
                    logger.info(
                        f"Preserved metadata for collection {collection_id}: {existing_metadata[collection_id]}"
                    )

        updates["pipelines"] = new_pipelines
        logger.info(f"Converted {len(request.bedrockKnowledgeBaseConfig.dataSources)} data sources to pipeline configs")

    # Handle direct pipeline updates (preserve existing metadata if not provided)
    elif "pipelines" in updates and updates["pipelines"] is not None and current_pipelines:
        # Create a mapping of existing pipeline metadata by collectionId
        existing_metadata = {
            pipeline.get("collectionId"): pipeline.get("metadata", {})
            for pipeline in current_pipelines
            if pipeline.get("collectionId")
        }

        # For each new pipeline, preserve existing metadata if metadata is not provided or incomplete
        for pipeline in updates["pipelines"]:
            collection_id = pipeline.get("collectionId")
            if collection_id and collection_id in existing_metadata:
                existing_meta = existing_metadata[collection_id]
                current_meta = pipeline.get("metadata", {})

                # If no metadata provided, use existing metadata
                if not current_meta:
                    pipeline["metadata"] = existing_meta
                    logger.info(f"Preserved complete metadata for collection {collection_id}: {existing_meta}")
                # If metadata provided but missing tags, preserve existing tags
                elif "tags" not in current_meta and "tags" in existing_meta:
                    pipeline["metadata"]["tags"] = existing_meta["tags"]
                    logger.info(f"Preserved tags for collection {collection_id}: " f"{existing_meta['tags']}")

    # Check if pipeline configuration has changed
    # Use the converted pipelines from updates if available, otherwise use request.pipelines
    new_pipelines = (
        updates.get("pipelines") if "pipelines" in updates else request.pipelines  # type: ignore[assignment]
    )

    # Validate immutable pipeline fields for existing repositories
    if new_pipelines is not None and current_pipelines:
        _validate_immutable_pipeline_fields(current_pipelines, new_pipelines)
    require_deployment = False

    if new_pipelines is not None:
        # For Bedrock KB repositories, only check if data source IDs (collectionIds) have changed
        if repository_type == RepositoryType.BEDROCK_KB:
            current_collection_ids = {p.get("collectionId") for p in (current_pipelines or []) if p.get("collectionId")}
            new_collection_ids = {p.get("collectionId") for p in new_pipelines if p.get("collectionId")}

            if current_collection_ids != new_collection_ids:
                added = new_collection_ids - current_collection_ids
                removed = current_collection_ids - new_collection_ids
                logger.info(f"Bedrock KB data sources changed: added={list(added)}, removed={list(removed)}")
                require_deployment = True
            else:
                logger.info("Bedrock KB data sources unchanged, no deployment needed")
        else:
            # For other repository types, check if pipelines were added/removed or immutable fields changed
            current_pipeline_keys = {_get_pipeline_key(p) for p in current_pipelines}
            new_pipeline_keys = {_get_pipeline_key(p) for p in new_pipelines}

            # Check if pipelines were added or removed
            if current_pipeline_keys != new_pipeline_keys:
                added = new_pipeline_keys - current_pipeline_keys  # type: ignore[assignment]
                removed = current_pipeline_keys - new_pipeline_keys
                logger.info(f"Pipeline changes detected: added={list(added)}, removed={list(removed)}")
                require_deployment = True
            else:
                # Check if any immutable fields changed (this would have been caught by validation above)
                # or if any other pipeline configuration changed
                require_deployment = new_pipelines != current_pipelines

    # Set status based on deployment requirement
    status = VectorStoreStatus.UPDATE_IN_PROGRESS if require_deployment else VectorStoreStatus.UPDATE_COMPLETE

    # Update repository
    updated_config: dict[str, Any] = vs_repo.update(repository_id, updates, status=status)

    # Trigger infrastructure deployment if pipeline changed
    if require_deployment:
        logger.info(f"Pipeline configuration changed for repository {repository_id}, triggering deployment")

        # Fetch the Step Function ARN from SSM Parameter Store
        parameter_name = os.environ["LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER"]
        state_machine_arn = ssm_client.get_parameter(Name=parameter_name)

        # Prepare input data for state machine (similar to create)
        serializer = TypeSerializer()
        rag_config = updated_config.copy()
        rag_config["repositoryId"] = repository_id
        # Remove status field - it will be set by the state machine
        rag_config.pop("status", None)

        input_data = {"ragConfig": rag_config}

        # Start Step Function execution
        response = step_functions_client.start_execution(
            stateMachineArn=state_machine_arn["Parameter"]["Value"],
            input=json.dumps(
                {
                    "body": input_data,
                    "config": {key: serializer.serialize(value) for key, value in rag_config.items()},
                }
            ),
        )

        logger.info(f"Started state machine execution: {response['executionArn']}")
        updated_config["executionArn"] = response["executionArn"]

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
        collections, _ = collection_service.list_collections(
            repository_id=repository_id,
            username="admin",
            user_groups=[],
            is_admin=True,
            page_size=1000,  # Get all collections
        )

        for collection in collections:
            try:
                logger.info(f"Deleting collection: {collection.collectionId}")
                collection_service.delete_collection(
                    collection_id=collection.collectionId,
                    repository_id=repository_id,
                    embedding_name=collection.embeddingModel if collection.default else None,
                    username="admin",
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


@api_wrapper
def list_bedrock_knowledge_bases(event: dict, context: dict) -> dict[str, Any]:
    """
    List all ACTIVE Bedrock Knowledge Bases in the AWS account.

    Marks KBs as unavailable if they're already associated with a repository.

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        Dictionary with:
            - knowledgeBases: List of ACTIVE Knowledge Base metadata with availability status
            - totalKnowledgeBases: Count of ACTIVE KBs

    Raises:
        ValidationError: If discovery fails
    """
    logger.info("Listing all ACTIVE Knowledge Bases")

    # Create bedrock-agent client
    bedrock_agent_client = boto3.client("bedrock-agent", region_name, config=retry_config)

    # Get all knowledge bases and filter to ACTIVE only
    all_kbs = list_knowledge_bases(bedrock_agent_client)
    active_kbs = [kb for kb in all_kbs if kb.status == "ACTIVE"]

    # Get all existing repositories to check which KBs are already in use
    existing_repos = vs_repo.get_registered_repositories()
    used_kb_ids = set()

    for repo in existing_repos:
        config = repo.get("config", {})
        bedrock_config = config.get("bedrockKnowledgeBaseConfig")
        if bedrock_config and isinstance(bedrock_config, dict):
            kb_id = bedrock_config.get("knowledgeBaseId")
            if kb_id:
                used_kb_ids.add(kb_id)

    # Convert to dictionaries and mark KBs as available or unavailable
    kb_list = []
    for kb in active_kbs:
        kb_dict = kb.model_dump(mode="json")
        kb_dict["available"] = kb.knowledgeBaseId not in used_kb_ids
        if not kb_dict["available"]:
            kb_dict["unavailableReason"] = "Already associated with another repository"
        kb_list.append(kb_dict)

    logger.info(
        f"Found {len(active_kbs)} ACTIVE Knowledge Bases out of {len(all_kbs)} total, "
        f"{len(used_kb_ids)} already in use"
    )

    return {"knowledgeBases": kb_list, "totalKnowledgeBases": len(kb_list)}


@api_wrapper
def list_bedrock_data_sources(event: dict, context: dict) -> dict[str, Any]:
    """
    List data sources for a specific Bedrock Knowledge Base.

    Args:
        event: Lambda event containing:
            - pathParameters.kbId: Knowledge Base ID
            - queryStringParameters.repositoryId (optional): Repository ID to check managed data sources
            - queryStringParameters.refresh (optional): Force refresh cache (default: false)
        context: Lambda context

    Returns:
        Dictionary with:
            - knowledgeBase: KB metadata (id, name, description)
            - availableDataSources: Data sources not yet managed
            - managedDataSources: Data sources already managed by collections
            - totalDataSources: Total count

    Raises:
        ValidationError: If KB not found or discovery fails
    """
    path_params = event.get("pathParameters", {})
    query_params = event.get("queryStringParameters") or {}

    kb_id = path_params.get("kbId")
    if not kb_id:
        raise ValidationError("kbId is required")

    repository_id = query_params.get("repositoryId")

    logger.info(f"Listing data sources for KB {kb_id}, repository={repository_id}")

    # Create bedrock-agent client
    bedrock_agent_client = boto3.client("bedrock-agent", region_name, config=retry_config)

    # Validate KB exists and get metadata
    kb_config = validate_bedrock_kb_exists(kb_id, bedrock_agent_client)

    # Get available and managed data sources
    data_sources = get_available_data_sources(
        kb_id=kb_id,
        repository_id=repository_id,
        bedrock_agent_client=bedrock_agent_client,
    )

    return {
        "knowledgeBase": {
            "id": kb_id,
            "name": kb_config.get("name"),
        },
        "dataSources": [ds.model_dump(mode="json") for ds in data_sources],
    }
