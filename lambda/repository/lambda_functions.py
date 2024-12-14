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
from typing import Any, Dict, List

import boto3
import requests
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from lisapy.langchain import LisaOpenAIEmbeddings
from models.domain_objects import IngestionType, RagDocument
from utilities.common_functions import api_wrapper, get_cert_path, get_id_token, retry_config
from utilities.exceptions import HTTPException
from utilities.file_processing import process_record
from utilities.validation import validate_model_name, ValidationError
from utilities.vector_store import find_repository_by_id, get_registered_repositories, get_vector_store_client

logger = logging.getLogger(__name__)
region_name = os.environ["AWS_REGION"]
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name, config=retry_config)
secrets_client = boto3.client("secretsmanager", region_name, config=retry_config)
iam_client = boto3.client("iam", region_name, config=retry_config)
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
doc_table = boto3.resource("dynamodb", region_name).Table(os.environ["RAG_DOCUMENT_TABLE"])
lisa_api_endpoint = ""


def _get_embeddings(model_name: str, id_token: str) -> LisaOpenAIEmbeddings:
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
    def __init__(self) -> None:
        try:
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
        if not texts:
            raise ValidationError("No texts provided for embedding")

        logger.info(f"Embedding {len(texts)} documents")
        try:
            url = f"{self.base_url}/embeddings"
            request_data = {"input": texts, "model": os.environ["EMBEDDING_MODEL"]}

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


def _get_embeddings_pipeline(model_name: str) -> Any:
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

    return PipelineEmbeddings()


@api_wrapper
def list_all(event: dict, context: dict) -> List[Dict[str, Any]]:
    """Return info on all available repositories.

    Currently, there is no support for dynamic repositories so only a single OpenSearch repository
    is returned.
    """

    user_groups = json.loads(event["requestContext"]["authorizer"]["groups"]) or []
    registered_repositories = get_registered_repositories()

    return list(
        filter(lambda repository: user_has_group(user_groups, repository["allowedGroups"]), registered_repositories)
    )


def user_has_group(user_groups: List[str], allowed_groups: List[str]) -> bool:
    """Returns if user groups has at least one intersections with allowed groups.

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

    repository = find_repository_by_id(repository_id)
    ensure_repository_access(event, repository)

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


def ensure_repository_access(event, repository):
    "Ensures a user has access to the repository or else raises an HTTPException"
    user_groups = json.loads(event["requestContext"]["authorizer"]["groups"]) or []
    if not user_has_group(user_groups, repository["allowedGroups"]):
        raise HTTPException(status_code=403, message="User does not have permission to access this repository")


@api_wrapper
def delete_document(event: dict, context: dict) -> Dict[str, Any]:
    """Purge all records related to the specified document from the RAG repository. If a documentId is supplied, a
    single document will be removed. If a documentName is supplied, all documents with that name will be removed

    Args:
        event (dict): The Lambda event object containing:
            - pathParameters.repositoryId: The repository id of VectorStore
            - queryStringParameters.collectionId: The collection identifier
            - queryStringParameters.repositoryType: Type of repository of VectorStore
            - queryStringParameters.documentId (optional): Name of document to purge
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

    query_string_params = event["queryStringParameters"]
    collection_id = query_string_params["collectionId"]
    repository_type = query_string_params["repositoryType"]
    document_id = query_string_params.get("documentId")
    document_name = query_string_params.get("documentName")

    if not document_id and not document_name:
        raise ValidationError("Either documentId or documentName must be specified")
    if document_id and document_name:
        raise ValidationError("Only one of documentId or documentName must be specified")

    docs = []
    if document_id:
        docs = [_get_document(document_id)]
    elif document_name:
        docs = _get_documents_by_name(document_name, repository_id, collection_id)

    if not docs:
        raise ValueError(f"No documents found in repository collection {repository_id}:{collection_id}")

    # Grab all sub document ids related to the parent document(s)
    subdoc_ids = [sub_doc for doc in docs for sub_doc in doc.get("sub_docs", [])]

    id_token = get_id_token(event)
    embeddings = _get_embeddings(model_name=collection_id, id_token=id_token)
    vs = get_vector_store_client(repository_type, index=collection_id, embeddings=embeddings)

    vs.delete(ids=subdoc_ids)

    with doc_table.batch_writer() as batch:
        for doc in docs:
            batch.delete_item(
                Key={
                     "pk":doc.get("pk"),
                    "document_id": doc.get("document_id")
                }
            )

    return {
        "documentName": docs[0].get("document_name"),
        "removedDocuments": len(docs),
        "removedDocumentChunks": len(subdoc_ids),
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

    repository = find_repository_by_id(repository_id)
    ensure_repository_access(event, repository)

    keys = body["keys"]
    docs = process_record(s3_keys=keys, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    texts = []  # list of strings
    metadatas = []  # list of dicts
    all_ids = []
    id_token = get_id_token(event)
    embeddings = _get_embeddings(model_name=model_name, id_token=id_token)
    vs = get_vector_store_client(repository_id, index=model_name, embeddings=embeddings)

    # Batch document ingestion one parent document at a time
    for doc_list in docs:
        with doc_table.batch_writer() as batch:
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
                sub_docs=ids,
                ingestion_type=IngestionType.MANUAL,
            )
            batch.put_item(Item=doc_entity.to_dict())

            all_ids.extend(ids)

    return {"ids": all_ids, "count": len(all_ids)}


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
    username = event["requestContext"]["authorizer"]["username"]

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

def get_groups(event: Any) -> List[str]:
    groups: List[str] = json.loads(event["requestContext"]["authorizer"]["groups"])
    return groups

@api_wrapper
def list_docs(event: dict, context: dict) -> list[RagDocument]:
    """List all documents for a given repository/collection.

    Args:
        event (dict): The Lambda event object containing query parameters
            - pathParameters.repositoryId: The repository id to list documents for
            - queryStringParameters.collectionId: The collection id to list documents for
        context (dict): The Lambda context object

    Returns:
        list[RagDocument]: A list of RagDocument objects representing all documents
            in the specified collection

    Raises:
        KeyError: If collectionId is not provided in queryStringParameters
    """

    path_params = event.get("pathParameters", {})
    repository_id = path_params.get("repositoryId")

    query_string_params = event.get("queryStringParameters", {})
    collection_id = query_string_params.get("collectionId")
    repository_type = query_string_params.get("repositoryType")
    pk = RagDocument.createPartitionKey(repository_id, collection_id)
    response = doc_table.query(
        KeyConditionExpression=Key("pk").eq(pk),
    )
    docs: list[RagDocument] = response["Items"]

    # Handle paginated Dynamo results
    while "LastEvaluatedKey" in response:
        response = doc_table.query(
            KeyConditionExpression=Key("pk").eq(pk),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        docs.extend(response["Items"])

    # return docs

    id_token = get_id_token(event)
    embeddings = _get_embeddings(model_name=collection_id, id_token=id_token)
    vs = get_vector_store_client(repository_type, index=collection_id, embeddings=embeddings)

    doc_search = vs.similarity_search(
        query="ML",
        k=1000,
    )
    doc_content = [{"name": doc.metadata["source"]} for doc in doc_search]
    logger.info(f"Found the following raw docs: {doc_content}")

    return docs


def _get_document(document_id: str) -> RagDocument:
    """Get a document from the RagDocTable.

    Args:
        document_id (str): The ID of the document to retrieve

    Returns:
        RagDocument: The document object

    Raises:
        KeyError: If the document is not found in the table
    """
    response = doc_table.query(IndexName="document_index", KeyConditionExpression=Key("document_id").eq(document_id))
    docs = response.get("Items")
    if not docs:
        raise KeyError(f"Document not found for document_id {document_id}")
    if len(docs) > 1:
        raise ValueError(f"Multiple items found for document_id {document_id}")

    logging.info(docs[0])

    return docs[0]


def _get_documents_by_name(document_name: str, repository_id: str, collection_id: str) -> list[RagDocument]:
    """Get a list of documents from the RagDocTable by name.

    Args:
        document_name (str): The name of the documents to retrieve
        repository_id (str): The repository id to list documents for
        collection_id (str): The collection id to list documents for

    Returns:
        list[RagDocument]: A list of document objects matching the specified name

    Raises:
        KeyError: If no documents are found with the specified name
    """
    pk = RagDocument.createPartitionKey(repository_id, collection_id)
    response = doc_table.query(
        KeyConditionExpression=Key("pk").eq(pk), FilterExpression=Key("document_name").eq(document_name)
    )
    docs: list[RagDocument] = response["Items"]

    # Handle paginated Dynamo results
    while "LastEvaluatedKey" in response:
        response = doc_table.query(
            KeyConditionExpression=Key("pk").eq(pk),
            FilterExpression=Key("document_name").eq(document_name),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        docs.extend(response["Items"])

    return docs
