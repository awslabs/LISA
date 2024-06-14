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
import create_env_variables  # noqa: F401
from botocore.config import Config
from lisapy.langchain import LisaOpenAIEmbeddings
from lisapy.utils import get_cert_path
from utilities.common_functions import api_wrapper, get_id_token, retry_config
from utilities.file_processing import process_record
from utilities.vector_store import get_vector_store_client

logger = logging.getLogger(__name__)
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)
s3 = session.client(
    "s3",
    region_name=os.environ["AWS_REGION"],
    config=Config(
        retries={
            "max_attempts": 3,
            "mode": "standard",
        },
        signature_version="s3v4",
    ),
)
lisa_api_endpoint = ""
registered_repositories: List[Dict[str, Any]] = []


def _get_embeddings(model_name: str, id_token: str) -> LisaOpenAIEmbeddings:
    global lisa_api_endpoint

    if not lisa_api_endpoint:
        lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
        lisa_api_endpoint = lisa_api_param_response["Parameter"]["Value"]

    base_url = f"{lisa_api_endpoint}/{os.environ['REST_API_VERSION']}/serve"

    embedding = LisaOpenAIEmbeddings(
        lisa_openai_api_base=base_url, model=model_name, api_token=id_token, verify=get_cert_path(iam_client)
    )
    return embedding


@api_wrapper
def list_all(event: dict, context: dict) -> List[Dict[str, Any]]:
    """Return info on all available repositories.

    Currently there is not support for dynamic repositories so only a single OpenSearch repository
    is returned.
    """
    global registered_repositories

    if not registered_repositories:
        registered_repositories_response = ssm_client.get_parameter(Name=os.environ["REGISTERED_REPOSITORIES_PS_NAME"])
        registered_repositories = json.loads(registered_repositories_response["Parameter"]["Value"])

    return registered_repositories


@api_wrapper
def similarity_search(event: dict, context: dict) -> Dict[str, Any]:
    """Return documents matching the query.

    Conducts similarity search against the vector store returning the top K
    documents based on the specified query. 'topK' can be set as an optional
    querystring parameter, if it is not specified the top 3 documents will be
    returned.
    """
    query_string_params = event["queryStringParameters"]
    model_name = query_string_params["modelName"]
    query = query_string_params["query"]
    repository_type = query_string_params["repositoryType"]
    top_k = query_string_params.get("topK", 3)

    id_token = get_id_token(event)

    embeddings = _get_embeddings(model_name=model_name, id_token=id_token)
    vs = get_vector_store_client(repository_type, index=model_name, embeddings=embeddings)
    docs = vs.similarity_search(
        query,
        k=top_k,
    )
    doc_content = [{"Document": {"page_content": doc.page_content, "metadata": doc.metadata}} for doc in docs]

    doc_return = {"docs": doc_content}
    logger.info(f"Returning: {doc_return}")
    return doc_return


@api_wrapper
def purge_document(event: dict, context: dict) -> Dict[str, Any]:
    """Purge all records related to the specified document from the RAG repository."""
    user_id = event["requestContext"]["authorizer"]["username"]
    repository_id = event["pathParameters"]["repositoryId"]
    document_id = event["pathParameters"]["sessionId"]

    logger.info(
        f"Purging records associated with document {document_id} "
        f"(requesting user: {user_id}), repository: {repository_id}"
    )

    return {"documentId": document_id, "recordsPurged": 0}


@api_wrapper
def ingest_documents(event: dict, context: dict) -> dict:
    """Ingest a set of documents into the specified repository."""
    body = json.loads(event["body"])
    embedding_model = body["embeddingModel"]
    model_name = embedding_model["modelName"]

    query_string_params = event["queryStringParameters"]
    repository_type = query_string_params["repositoryType"]
    chunk_size = int(query_string_params["chunkSize"]) if "chunkSize" in query_string_params else None
    chunk_overlap = int(query_string_params["chunkOverlap"]) if "chunkOverlap" in query_string_params else None

    docs = process_record(s3_keys=body["keys"], chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    texts = []  # list of strings
    metadatas = []  # list of dicts

    for doc_list in docs:
        for doc in doc_list:
            texts.append(doc.page_content)
            metadatas.append(doc.metadata)

    id_token = get_id_token(event)
    embeddings = _get_embeddings(model_name=model_name, id_token=id_token)
    vs = get_vector_store_client(repository_type, index=model_name, embeddings=embeddings)
    ids = vs.add_texts(texts=texts, metadatas=metadatas)
    return {"ids": ids, "count": len(ids)}


@api_wrapper
def presigned_url(event: dict, context: dict) -> dict:
    """Generate a pre-signed URL for uploading files to the RAG ingest bucket."""
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
