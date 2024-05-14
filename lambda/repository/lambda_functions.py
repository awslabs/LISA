"""
Lambda functions for RAG repository API.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
import json
import logging
import os
import tempfile
from typing import Any, Dict, List

import boto3
import create_env_variables  # noqa: F401
from botocore.config import Config
from lisapy.langchain import Lisa, LisaEmbeddings
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
rest_api_cert_path = ""


def _get_cert_path() -> str | bool:
    global rest_api_cert_path

    if not rest_api_cert_path:
        # If no SSL Cert ARN is specified just default verify to true and the cert will need to be
        # signed by a known CA
        # Assume cert is signed with known CA if coming from ACM
        cert_arn = os.environ["RESTAPI_SSL_CERT_ARN"]
        if not cert_arn or cert_arn.split(":")[2] == "acm":
            return True

        # We have the arn but we need the name which is the last part of the arn
        rest_api_cert = iam_client.get_server_certificate(ServerCertificateName=cert_arn.split("/")[1])
        cert_body = rest_api_cert["ServerCertificate"]["CertificateBody"]
        cert_file = tempfile.NamedTemporaryFile(delete=False)
        cert_file.write(cert_body.encode("utf-8"))
        rest_api_cert_path = cert_file.name

    return rest_api_cert_path


def _get_embeddings(provider: str, model_name: str, id_token: str) -> LisaEmbeddings:
    global lisa_api_endpoint

    if not lisa_api_endpoint:
        lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
        lisa_api_endpoint = lisa_api_param_response["Parameter"]["Value"]

    lisa = Lisa(
        url=lisa_api_endpoint, verify=_get_cert_path(), timeout=60, headers={"Authorization": f"Bearer {id_token}"}
    )

    embedding = LisaEmbeddings(provider=provider, model_name=model_name, client=lisa)
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
    model_provider = query_string_params["modelProvider"]
    query = query_string_params["query"]
    repository_type = query_string_params["repositoryType"]
    top_k = query_string_params.get("topK", 3)

    id_token = get_id_token(event)

    embeddings = _get_embeddings(provider=model_provider, model_name=model_name, id_token=id_token)
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
    model_provider = embedding_model["provider"]

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
    embeddings = _get_embeddings(provider=model_provider, model_name=model_name, id_token=id_token)
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
