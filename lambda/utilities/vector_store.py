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

"""Helper to return Langchain vector store corresponding to backing store."""
import json
import logging
import os

import boto3
from langchain_community.vectorstores.opensearch_vector_search import OpenSearchVectorSearch
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from utilities.common_functions import retry_config

from . import create_env_variables  # noqa type: ignore

opensearch_endpoint = ""
logger = logging.getLogger(__name__)
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
secretsmanager_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)


def get_vector_store_client(repository_id: str, index: str, embeddings: Embeddings) -> VectorStore:
    """Return Langchain VectorStore corresponding to the specified store.

    Creates a langchain vector store based on the specified embeddigs adapter and backing store.
    """
    prefix = os.environ.get("REGISTERED_REPOSITORIES_PS_PREFIX")
    connection_info = ssm_client.get_parameter(Name=f"{prefix}{repository_id}")
    connection_info = json.loads(connection_info["Parameter"]["Value"])
    if connection_info.get("type") == "opensearch":
        service = "es"
        credentials = session.get_credentials()

        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            session.region_name,
            service,
            session_token=credentials.token,
        )

        opensearch_endpoint = f"https://{connection_info.get('endpoint')}"

        return OpenSearchVectorSearch(
            opensearch_url=opensearch_endpoint,
            index_name=index,
            embedding_function=embeddings,
            http_auth=auth,
            timeout=300,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )

    elif connection_info.get("type") == "pgvector":
        secrets_response = secretsmanager_client.get_secret_value(SecretId=connection_info.get("passwordSecretId"))
        password = json.loads(secrets_response.get("SecretString")).get("password")

        connection_string = PGVector.connection_string_from_db_params(
            driver="psycopg2",
            host=connection_info.get("dbHost"),
            port=connection_info.get("dbPort"),
            database=connection_info.get("dbName"),
            user=connection_info.get("username"),
            password=password,
        )
        return PGVector(
            collection_name=index,
            connection_string=connection_string,
            embedding_function=embeddings,
        )

    raise ValueError(f"Unrecognized RAG store: '{repository_id}'")
