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
from models.domain_objects import FixedChunkingStrategy, IngestionJob, IngestionStatus, ListJobsResponse, RagDocument
from repository.embeddings import RagEmbeddings
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.auth import admin_only, get_username, is_admin
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
            - queryStringParameters.modelName: Name of the embedding model
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
    model_name = query_string_params["modelName"]
    query = query_string_params["query"]
    top_k = query_string_params.get("topK", 3)
    include_score = query_string_params.get("score", "false").lower() == "true"
    repository_id = event["pathParameters"]["repositoryId"]

    repository = vs_repo.find_repository_by_id(repository_id)
    _ensure_repository_access(event, repository)

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
        embeddings = RagEmbeddings(model_name=model_name, id_token=id_token)
        vs = get_vector_store_client(repository_id, index=model_name, embeddings=embeddings)

        # empty vector stores do not have an initialize index. Return empty docs
        if RepositoryType.is_type(repository, RepositoryType.OPENSEARCH) and not vs.client.indices.exists(
            index=model_name
        ):
            logger.info(f"Index {model_name} does not exist. Returning empty docs.")
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


def _ensure_repository_access(event: dict[str, Any], repository: dict[str, Any]) -> None:
    """Ensures a user has access to the repository or else raises an HTTPException"""
    if is_admin(event) is False:
        user_groups = json.loads(event["requestContext"]["authorizer"]["groups"]) or []
        if not user_has_group_access(user_groups, repository.get("allowedGroups", [])):
            raise HTTPException(status_code=403, message="User does not have permission to access this repository")


def _ensure_document_ownership(event: dict[str, Any], docs: list[dict[str, Any]]) -> None:
    """Verify ownership of documents"""
    username = get_username(event)
    if is_admin(event) is False:
        for doc in docs:
            if not (doc.get("username") == username):
                raise ValueError(f"Document {doc.get('document_id')} is not owned by {username}")


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

    _ensure_repository_access(event, vs_repo.find_repository_by_id(repository_id))

    rag_documents: list[RagDocument] = []
    if document_ids:
        rag_documents = [doc_repo.find_by_id(document_id=document_id) for document_id in document_ids]

    if not rag_documents:
        raise ValueError(f"No documents found in repository collection {repository_id}:{collection_id}")

    _ensure_document_ownership(event, rag_documents)

    # todo don't delete object from s3 if still referenced by another repository/collection
    # delete s3 files if
    doc_repo.delete_s3_docs(repository_id, rag_documents)

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

    return {"documentIds": document_ids}


@api_wrapper
def ingest_documents(event: dict, context: dict) -> dict:
    """Ingest documents into the RAG repository.

    Args:
        event (dict): The Lambda event object containing:
            - body.embeddingModel.modelName: Document collection id
            - body.keys: List of s3 keys to ingest
            - pathParameters.repositoryId: Repository id (VectorStore)
            - queryStringParameters.repositoryType: Repository type (VectorStore)
            - queryStringParameters.chunkSize (optional): Size of text chunks
            - queryStringParameters.chunkOverlap (optional): Overlap between chunks
        context (dict): The Lambda context object

    Returns:
        dict: A dictionary containing:
            - ids (list): List of generated document IDs
            - count (int): Total number of documents ingested

    Raises:
        ValidationError: If required parameters are missing or invalid
    """
    body = json.loads(event["body"])
    embedding_model = body["embeddingModel"]
    model_name = embedding_model["modelName"]
    bucket = os.environ["BUCKET_NAME"]

    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    query_string_params = event["queryStringParameters"]
    chunk_size = int(query_string_params["chunkSize"]) if "chunkSize" in query_string_params else None
    chunk_overlap = int(query_string_params["chunkOverlap"]) if "chunkOverlap" in query_string_params else None
    logger.info(f"using repository {repository_id}")

    username = get_username(event)
    repository = vs_repo.find_repository_by_id(repository_id)
    _ensure_repository_access(event, repository)

    ingestion_document_ids = []
    for key in body["keys"]:
        job = IngestionJob(
            repository_id=repository_id,
            collection_id=model_name,
            chunk_strategy=FixedChunkingStrategy(size=str(chunk_size), overlap=str(chunk_overlap)),
            s3_path=f"s3://{bucket}/{key}",
            username=username,
        )
        ingestion_job_repository.save(job)
        ingestion_service.create_ingest_job(job)
        ingestion_document_ids.append(job.id)

    return {"ingestionJobIds": ingestion_document_ids}


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

    _ensure_repository_access(event, vs_repo.find_repository_by_id(repository_id))
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

    page_size = int(query_string_params.get("pageSize", "10"))

    if page_size < 1:
        page_size = 1
    elif page_size > 100:  # Cap at 100 to prevent abuse
        page_size = 100

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
def list_jobs(event: dict, context: dict) -> ListJobsResponse:
    """List ingestion jobs for a specific repository with filtering and pagination.

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository id to list jobs for
            - queryStringParameters.timeLimit (optional): Time limit in hours (default: 720, which is 30 days)
            - queryStringParameters.pageSize (optional): Number of jobs to return per page (default: 10, max: 100)
            - queryStringParameters.lastEvaluatedKey (optional): Pagination token from previous request
        context (dict): The Lambda context object

    Returns:
        ListJobsResponse: A response object containing:
            - jobs: List of job objects with their details
            - lastEvaluatedKey: Token for next page (null if no more pages)
            - hasNextPage: Boolean indicating if more pages exist
            - hasPreviousPage: Boolean indicating if previous pages exist

    Raises:
        ValidationError: If repositoryId is not provided
    """
    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    if not repository_id:
        raise ValidationError("repositoryId is required")

    # Ensure user has access to the repository
    repository = vs_repo.find_repository_by_id(repository_id)
    _ensure_repository_access(event, repository)

    username = get_username(event)
    admin = is_admin(event)

    query_params = event.get("queryStringParameters", {}) or {}
    time_limit_hours = int(query_params.get("timeLimit", "720"))  # Default to 30 days (720 hours)
    
    # Handle pagination parameters
    page_size = int(query_params.get("pageSize", "10"))
    if page_size < 1:
        page_size = 1
    elif page_size > 100:  # Cap at 100 to prevent abuse
        page_size = 100

    # Parse lastEvaluatedKey if provided
    last_evaluated_key: Optional[Dict[str, str]] = None
    if "lastEvaluatedKey" in query_params:
        try:
            last_evaluated_key = json.loads(urllib.parse.unquote(query_params["lastEvaluatedKey"]))
        except (json.JSONDecodeError, TypeError):
            # If parsing fails, start from beginning
            last_evaluated_key = None

    logger.info(f"Calling list_jobs_by_repository with: repository_id={repository_id}, username={username}, is_admin={admin}, time_limit_hours={time_limit_hours}, page_size={page_size}")
    
    jobs, last_evaluated_key = ingestion_job_repository.list_jobs_by_repository(
        repository_id=repository_id, 
        username=username, 
        is_admin=admin, 
        time_limit_hours=time_limit_hours,
        page_size=page_size,
        last_evaluated_key=last_evaluated_key
    )

    logger.info(f"Retrieved {len(jobs)} jobs from repository")
    for job in jobs:
        logger.info(f"Job: {job.id} - {job.status} - {job.created_date}")

    return ListJobsResponse(
        jobs=jobs,
        lastEvaluatedKey=last_evaluated_key,
        hasNextPage=last_evaluated_key is not None,
        hasPreviousPage="lastEvaluatedKey" in query_params,
    )


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
@admin_only
def delete(event: dict, context: dict) -> Any:
    """
    Delete a vector store process using AWS Step Functions. This function ensures
    that the user is an administrator or owns the vector store being deleted.

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
    model_name = path_params.get("modelName", None)
    if not model_name:
        raise ValidationError("modelName is required")

    repository = vs_repo.find_repository_by_id(repository_id=repository_id)
    id_token = get_id_token(event)
    embeddings = RagEmbeddings(model_name=model_name, id_token=id_token)
    vs = get_vector_store_client(repository_id, index=model_name, embeddings=embeddings)

    try:
        if RepositoryType.is_type(repository, RepositoryType.OPENSEARCH):
            if vs.client.indices.exists(index=model_name):
                vs.client.indices.delete(index=model_name)
                logger.info(f"Deleted OpenSearch index: {model_name}")
            else:
                logger.info(f"OpenSearch index {model_name} does not exist")
        elif RepositoryType.is_type(repository, RepositoryType.PGVECTOR):
            # For PGVector, delete all documents in the collection
            vs.delete_collection()
            logger.info(f"Deleted PGVector collection: {model_name}")
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
