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
from typing import Any, cast, Dict, List

import boto3
import requests
from boto3.dynamodb.types import TypeSerializer
from botocore.config import Config
from langchain_core.vectorstores import VectorStore
from lisapy.langchain import LisaOpenAIEmbeddings
from models.domain_objects import ChunkStrategyType, IngestionType, RagDocument
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.common_functions import (
    admin_only,
    api_wrapper,
    get_cert_path,
    get_groups,
    get_id_token,
    get_username,
    is_admin,
    retry_config,
)
from utilities.exceptions import HTTPException
from utilities.file_processing import process_record
from utilities.validation import validate_model_name, ValidationError
from utilities.vector_store import get_vector_store_client

logger = logging.getLogger(__name__)
region_name = os.environ["AWS_REGION"]
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name, config=retry_config)
secrets_client = boto3.client("secretsmanager", region_name, config=retry_config)
iam_client = boto3.client("iam", region_name, config=retry_config)
step_functions_client = boto3.client("stepfunctions", region_name, config=retry_config)
ddb_client = boto3.client("dynamodb", region_name, config=retry_config)
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
lisa_api_endpoint = ""
doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])
vs_repo = VectorStoreRepository()


def _get_embeddings(model_name: str, id_token: str) -> LisaOpenAIEmbeddings:
    """
    Initialize and return an embeddings client for the specified model.

    Args:
        model_name: Name of the embedding model to use
        id_token: Authentication token for API access

    Returns:
        LisaOpenAIEmbeddings: Configured embeddings client
    """
    global lisa_api_endpoint

    if not lisa_api_endpoint:
        lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
        lisa_api_endpoint = lisa_api_param_response["Parameter"]["Value"]

    base_url = f"{lisa_api_endpoint}/{os.environ['REST_API_VERSION']}/serve"
    cert_path = get_cert_path(iam_client)

    embedding = LisaOpenAIEmbeddings(
        lisa_openai_api_base=base_url, model=model_name, api_token=id_token, verify=cert_path
    )
    return embedding

    # Create embeddings client that matches LisaOpenAIEmbeddings interface


class PipelineEmbeddings:
    """
    Handles document embeddings for pipeline processing using management credentials.

    This class provides methods to embed both single queries and batches of documents
    using the LISA API with management-level authentication.
    """

    model_name: str

    def __init__(self, model_name: str) -> None:
        try:
            self.model_name = model_name
            # Get the management key secret name from SSM Parameter Store
            secret_name_param = ssm_client.get_parameter(Name=os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"])
            secret_name = secret_name_param["Parameter"]["Value"]

            # Get the management token from Secrets Manager using the secret name
            secret_response = secrets_client.get_secret_value(SecretId=secret_name)
            self.token = secret_response["SecretString"]

            # Get the API endpoint from SSM
            lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
            self.base_url = f"{lisa_api_param_response['Parameter']['Value']}/{os.environ['REST_API_VERSION']}/serve"

            # Get certificate path for SSL verification
            self.cert_path = get_cert_path(iam_client)

            logger.info("Successfully initialized pipeline embeddings")
        except Exception:
            logger.error("Failed to initialize pipeline embeddings", exc_info=True)
            raise

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ValidationError: If input texts are invalid
            Exception: If embedding request fails
        """
        if not texts:
            raise ValidationError("No texts provided for embedding")

        logger.info(f"Embedding {len(texts)} documents")
        try:
            url = f"{self.base_url}/embeddings"
            request_data = {"input": texts, "model": self.model_name}

            response = requests.post(
                url,
                json=request_data,
                headers={"Authorization": self.token, "Content-Type": "application/json"},
                verify=self.cert_path,  # Use proper SSL verification
                timeout=300,  # 5 minute timeout
            )

            if response.status_code != 200:
                logger.error(f"Embedding request failed with status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                raise Exception(f"Embedding request failed with status {response.status_code}")

            result = response.json()
            logger.debug(f"API Response: {result}")  # Log the full response for debugging

            # Handle different response formats
            embeddings = []
            if isinstance(result, dict):
                if "data" in result:
                    # OpenAI-style format
                    for item in result["data"]:
                        if isinstance(item, dict) and "embedding" in item:
                            embeddings.append(item["embedding"])
                        else:
                            embeddings.append(item)  # Assume the item itself is the embedding
                else:
                    # Try to find embeddings in the response
                    for key in ["embeddings", "embedding", "vectors", "vector"]:
                        if key in result:
                            embeddings = result[key]
                            break
            elif isinstance(result, list):
                # Direct list format
                embeddings = result

            if not embeddings:
                logger.error(f"Could not find embeddings in response: {result}")
                raise Exception("No embeddings found in API response")

            if len(embeddings) != len(texts):
                logger.error(f"Mismatch between number of texts ({len(texts)}) and embeddings ({len(embeddings)})")
                raise Exception("Number of embeddings does not match number of input texts")

            logger.info(f"Successfully embedded {len(texts)} documents")
            return embeddings

        except requests.Timeout:
            logger.error("Embedding request timed out")
            raise Exception("Embedding request timed out after 5 minutes")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to get embeddings: {str(e)}", exc_info=True)
            raise

    def embed_query(self, text: str) -> List[float]:
        if not text or not isinstance(text, str):
            raise ValidationError("Invalid query text")

        logger.info("Embedding single query text")
        return self.embed_documents([text])[0]


def get_embeddings_pipeline(model_name: str) -> Any:
    """
    Get embeddings for pipeline requests using management token.

    Args:
        model_name: Name of the embedding model to use

    Raises:
        ValidationError: If model name is invalid
        Exception: If API request fails
    """
    logger.info("Starting pipeline embeddings request")
    validate_model_name(model_name)

    return PipelineEmbeddings(model_name=model_name)


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
        if admin_override or user_has_group(user_groups, repo.get("allowedGroups", []))
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


def user_has_group(user_groups: List[str], allowed_groups: List[str]) -> bool:
    """Returns if user groups has at least one intersection with allowed groups.

    If allowed groups is empty this will return True.
    """

    if len(allowed_groups) > 0:
        return len(set(user_groups).intersection(set(allowed_groups))) > 0
    else:
        return True


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
    repository_id = event["pathParameters"]["repositoryId"]

    repository = vs_repo.find_repository_by_id(repository_id)
    _ensure_repository_access(event, repository)

    id_token = get_id_token(event)

    embeddings = _get_embeddings(model_name=model_name, id_token=id_token)
    vs = get_vector_store_client(repository_id, index=model_name, embeddings=embeddings)
    docs = vs.similarity_search(
        query,
        k=top_k,
    )
    doc_content = [{"Document": {"page_content": doc.page_content, "metadata": doc.metadata}} for doc in docs]

    doc_return = {"docs": doc_content}
    logger.info(f"Returning: {doc_return}")
    return doc_return


def _ensure_repository_access(event: dict[str, Any], repository: dict[str, Any]) -> None:
    """Ensures a user has access to the repository or else raises an HTTPException"""
    if is_admin(event) is False:
        user_groups = json.loads(event["requestContext"]["authorizer"]["groups"]) or []
        if not user_has_group(user_groups, repository.get("allowedGroups", [])):
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
    document_name = query_string_params.get("documentName")

    if not document_ids and not document_name:
        raise ValidationError("No 'documentIds' or 'documentName' parameter supplied")
    if document_ids and document_name:
        raise ValidationError("Only one of documentIds or documentName must be specified")
    if not collection_id and document_name:
        raise ValidationError("A 'collectionId' must be included to delete a document by name")

    _ensure_repository_access(event, vs_repo.find_repository_by_id(repository_id))

    docs: list[RagDocument.model_dump] = []
    if document_ids:
        docs = [
            doc_repo.find_by_id(repository_id=repository_id, document_id=doc_id, join_docs=True)
            for doc_id in document_ids
        ]
    elif document_name:
        docs = doc_repo.find_by_name(
            repository_id=repository_id, collection_id=collection_id, document_name=document_name, join_docs=True
        )

    if not docs:
        raise ValueError(f"No documents found in repository collection {repository_id}:{collection_id}")

    _ensure_document_ownership(event, docs)

    id_token = get_id_token(event)
    vs_collection_map: dict[str, VectorStore] = {}
    for doc in docs:
        # Get vector store for document collection
        collection_id = doc.get("collection_id")
        vs = vs_collection_map.get(collection_id)
        if not vs:
            embeddings = _get_embeddings(model_name=collection_id, id_token=id_token)
            vs = get_vector_store_client(repository_id=repository_id, index=collection_id, embeddings=embeddings)
            vs_collection_map[collection_id] = vs
        # Delete all document chunks from vector store collection
        vs.delete(ids=doc.get("subdocs"))

    for doc in docs:
        doc_repo.delete_by_id(repository_id=repository_id, document_id=doc.get("document_id"))

    # Collect all document parts for summary of deletion
    doc_ids = {doc.get("document_id") for doc in docs}
    subdoc_ids = []
    for doc in docs:
        subdoc_ids.extend(doc.get("subdocs"))

    removedS3 = doc_repo.delete_s3_docs(repository_id, docs)

    doc_names = [f"{doc.get('repository_id')}/{doc.get('collection_id')}/{doc.get('document_name')}" for doc in docs]

    return {
        "documents": doc_names,
        "removedDocuments": len(doc_ids),
        "removedDocumentChunks": len(subdoc_ids),
        "removedS3Documents": removedS3,
    }


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

    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    query_string_params = event["queryStringParameters"]
    chunk_size = int(query_string_params["chunkSize"]) if "chunkSize" in query_string_params else None
    chunk_overlap = int(query_string_params["chunkOverlap"]) if "chunkOverlap" in query_string_params else None
    logger.info(f"using repository {repository_id}")

    username = get_username(event)
    repository = vs_repo.find_repository_by_id(repository_id)
    _ensure_repository_access(event, repository)

    keys = body["keys"]
    docs = process_record(s3_keys=keys, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    texts = []  # list of strings
    metadatas = []  # list of dicts
    doc_entities = []
    id_token = get_id_token(event)
    embeddings = _get_embeddings(model_name=model_name, id_token=id_token)
    vs = get_vector_store_client(repository_id, index=model_name, embeddings=embeddings)

    # Batch document ingestion one parent document at a time
    for doc_list in docs:
        document_name = doc_list[0].metadata.get("name")
        doc_source = doc_list[0].metadata.get("source")
        for doc in doc_list:
            texts.append(doc.page_content)
            metadatas.append(doc.metadata)
        # Ingest document into vector store
        ids = vs.add_texts(texts=texts, metadatas=metadatas)

        # Add document to RagDocTable
        doc_entity = RagDocument(
            repository_id=repository_id,
            collection_id=model_name,
            document_name=document_name,
            source=doc_source,
            subdocs=ids,
            username=username,
            chunk_strategy={
                "type": ChunkStrategyType.FIXED.value,
                "size": str(chunk_size),
                "overlap": str(chunk_overlap),
            },
            ingestion_type=IngestionType.MANUAL,
        )
        doc_repo.save(doc_entity)
        doc_entities.append(doc_entity)

    doc_ids = (doc.document_id for doc in doc_entities)
    subdoc_ids = [sub_id for doc in doc_entities for sub_id in doc.subdocs]
    return {
        "documentIds": doc_ids,
        "chunkCount": len(subdoc_ids),
    }


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
    doc = doc_repo.find_by_id(repository_id=repository_id, document_id=document_id)

    source = doc.get("source")
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
def list_docs(event: dict, context: dict) -> dict[str, list[RagDocument.model_dump] | str | None]:
    """List all documents for a given repository/collection.

    Args:
        event (dict): The Lambda event object containing query parameters
            - pathParameters.repositoryId: The repository id to list documents for
            - queryStringParameters.collectionId: The collection id to list documents for
        context (dict): The Lambda context object

    Returns:
        Tuple list[RagDocument], dict[lastEvaluatedKey]: A list of RagDocument objects representing all documents
            in the specified collection and the last evaluated key for pagination

    Raises:
        KeyError: If collectionId is not provided in queryStringParameters
    """

    path_params = event.get("pathParameters", {}) or {}
    repository_id = path_params.get("repositoryId")

    query_string_params = event.get("queryStringParameters", {}) or {}
    collection_id = query_string_params.get("collectionId")
    last_evaluated = query_string_params.get("lastEvaluated")

    docs, last_evaluated = doc_repo.list_all(
        repository_id=repository_id, collection_id=collection_id, last_evaluated_key=last_evaluated
    )
    return {"documents": docs, "lastEvaluated": last_evaluated}


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
