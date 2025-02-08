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
from typing import Any, cast, List

import boto3
import create_env_variables  # noqa: F401
from langchain_community.vectorstores.opensearch_vector_search import OpenSearchVectorSearch
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from utilities.common_functions import retry_config
from utilities.encoders import convert_decimal

opensearch_endpoint = ""
logger = logging.getLogger(__name__)
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
secretsmanager_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
ddb_client = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
ddb_client = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
ddb_table = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)


def get_registered_repositories() -> List[dict]:
    """Get a list of all registered RAG repositories."""
    table_name = os.environ["LISA_RAG_VECTOR_STORE_TABLE"]
    try:
        table = ddb_table.Table(table_name)
        response = table.scan()
        items = response["Items"]
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response["Items"])
        # Convert all ddb Numbers to floats to correctly serialize to json
        items = convert_decimal(items)
        return [item["config"] for item in items if "config" in item]
    except ddb_client.exceptions.ResourceNotFoundException:
        raise ValueError(f"Table '{table_name}' does not exist")
    except Exception as e:
        raise e


def get_repository_status() -> dict[str, str]:
    """Get a list the status of all repositories"""
    table_name = os.environ["LISA_RAG_VECTOR_STORE_TABLE"]
    status = {}

    try:
        table = ddb_table.Table(table_name)
        response = table.scan(ProjectionExpression="repositoryId, status")
        items = response["Items"]
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"], ProjectionExpression="repositoryId, status"
            )
            items.extend(response["Items"])

        status = {item["repositoryId"]: item["config"] for item in items if "config" in item}

    except ddb_client.exceptions.ResourceNotFoundException:
        raise ValueError(f"Table '{table_name}' does not exist")
    return status


def find_repository_by_id(repository_id: str, raw_config: bool = False) -> dict[str, Any]:
    """
    Find a repository by its ID.

    Args:
        repository_id: The ID of the repository to find.
        raw_config: return the full object in dynamo, instead of just the repository config portion
    Returns:
        The repository configuration.

    Raises:
        ValueError: If the repository is not found or the table does not exist.
    """
    table_name = os.environ["LISA_RAG_VECTOR_STORE_TABLE"]
    try:
        response = ddb_table.Table(table_name).get_item(
            Key={"repositoryId": repository_id},
        )
    except Exception as e:
        raise ValueError(f"Failed to update repository: {repository_id}", e)

    if "Item" not in response:
        raise ValueError(f"Repository with ID '{repository_id}' not found")

    repository: dict[str, Any] = convert_decimal(response.get("Item"))
    return repository if raw_config else cast(dict[str, Any], repository.get("config", {}))


def update_repository(repository: dict[str, Any]) -> None:
    table_name = os.environ["LISA_RAG_VECTOR_STORE_TABLE"]
    logging.info(f"update_repository: {repository}")
    ddb_table.Table(table_name).put_item(Item=repository)


def get_vector_store_client(repository_id: str, index: str, embeddings: Embeddings) -> VectorStore:
    """Return Langchain VectorStore corresponding to the specified store.

    Creates a langchain vector store based on the specified embeddigs adapter and backing store.
    """
    repository = find_repository_by_id(repository_id)
    repository_type = repository.get("type")

    if repository_type == "opensearch":
        service = "es"
        session = boto3.Session()
        credentials = session.get_credentials()

        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            session.region_name,
            service,
            session_token=credentials.token,
        )

        return OpenSearchVectorSearch(
            opensearch_url=repository.get("opensearchConfig", {}).get("endpoint"),
            index_name=index,
            embedding_function=embeddings,
            http_auth=auth,
            timeout=300,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )

    elif repository_type == "pgvector":

        rdsConfig = repository.get("rdsConfig", {})
        secrets_response = secretsmanager_client.get_secret_value(SecretId=rdsConfig.get("passwordSecretId"))
        password = json.loads(secrets_response["SecretString"])["password"]

        connection_string = PGVector.connection_string_from_db_params(
            driver="psycopg2",
            host=rdsConfig["dbHost"],
            port=rdsConfig["dbPort"],
            database=rdsConfig["dbName"],
            user=rdsConfig["username"],
            password=password,
        )
        return PGVector(
            collection_name=index,
            connection_string=connection_string,
            embedding_function=embeddings,
        )

    raise ValueError(f"Unrecognized RAG store: '{repository_id}'")
