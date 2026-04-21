#!/usr/bin/env python3
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

"""
Common utilities for LISA integration tests.

This module provides reusable functions for:
- Authentication setup (re-exported from lisapy.authentication)
- API client creation
- Resource management
- Waiting for resources to be ready
"""

import logging
import os
import sys
import time
from collections.abc import Callable

import boto3

# Add lisa-sdk to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lisa-sdk"))

from lisapy.api import LisaApi
from lisapy.authentication import create_api_token, get_management_key, setup_authentication

logger = logging.getLogger(__name__)

# Re-export so existing consumers (e.g. conftest.py) continue to work.
__all__ = [
    "get_management_key",
    "create_api_token",
    "setup_authentication",
    "create_lisa_client",
    "wait_for_resource_ready",
    "get_dynamodb_table",
    "get_s3_client",
    "verify_document_in_dynamodb",
    "verify_document_in_s3",
    "verify_document_not_in_s3",
    "get_table_names_from_env",
]


def create_lisa_client(
    api_url: str,
    deployment_name: str,
    region: str | None = None,
    verify_ssl: bool = True,
    timeout: int = 10,
    deployment_stage: str | None = None,
) -> LisaApi:
    """Create and configure a LISA API client.

    Args:
        api_url: The LISA API URL
        deployment_name: The LISA deployment name for authentication
        region: AWS region (optional, uses default if not provided)
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        deployment_stage: The deployment stage (optional)

    Returns:
        LisaApi: Configured LISA API client

    Raises:
        Exception: If client creation fails
    """
    logger.info(f"Creating LISA client for {api_url}")

    auth_headers = setup_authentication(deployment_name, region, deployment_stage)
    client = LisaApi(url=api_url, headers=auth_headers, verify=verify_ssl, timeout=timeout)

    logger.info("LISA client created successfully")
    return client


def wait_for_resource_ready(
    check_func: Callable[[], bool],
    resource_type: str,
    resource_id: str,
    max_wait_seconds: int = 1800,
    check_interval_seconds: int = 15,
) -> bool:
    """Wait for a resource to be ready.

    Args:
        check_func: Function that returns True when resource is ready
        resource_type: Type of resource (for logging)
        resource_id: ID of the resource (for logging)
        max_wait_seconds: Maximum seconds to wait (default: 30 minutes)
        check_interval_seconds: Seconds between checks (default: 15 seconds)

    Returns:
        bool: True if resource is ready, False if timeout

    Raises:
        Exception: If check function raises an exception
    """
    logger.info(f"Waiting for {resource_type} '{resource_id}' to be ready...")

    max_iterations = max_wait_seconds // check_interval_seconds
    for i in range(max_iterations):
        try:
            if check_func():
                logger.info(f"{resource_type} '{resource_id}' is ready!")
                return True
        except Exception as e:
            logger.debug(f"Check failed: {e}")

        if i < max_iterations - 1:
            logger.debug(f"Still waiting... ({i+1}/{max_iterations})")
            time.sleep(check_interval_seconds)

    logger.warning(f"Timeout waiting for {resource_type} '{resource_id}' to be ready")
    return False


def get_dynamodb_table(table_name: str, region: str | None = None):
    """Get a DynamoDB table resource.

    Args:
        table_name: Name of the DynamoDB table
        region: AWS region (optional, uses default if not provided)

    Returns:
        boto3 Table resource

    Raises:
        Exception: If table cannot be accessed
    """
    try:
        dynamodb = boto3.resource("dynamodb", region_name=region) if region else boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        return table
    except Exception as e:
        logger.error(f"Failed to get DynamoDB table {table_name}: {e}")
        raise


def get_s3_client(region: str | None = None):
    """Get an S3 client.

    Args:
        region: AWS region (optional, uses default if not provided)

    Returns:
        boto3 S3 client

    Raises:
        Exception: If client cannot be created
    """
    try:
        return boto3.client("s3", region_name=region) if region else boto3.client("s3")
    except Exception as e:
        logger.error(f"Failed to create S3 client: {e}")
        raise


def verify_document_in_dynamodb(
    document_id: str,
    table_name: str,
    expected_collection_id: str | None = None,
    region: str | None = None,
) -> bool:
    """Verify a document exists in DynamoDB.

    Args:
        document_id: The document ID to verify
        table_name: Name of the documents table
        expected_collection_id: Expected collection ID (optional)
        region: AWS region (optional, uses default if not provided)

    Returns:
        bool: True if document exists and matches expectations

    Raises:
        Exception: If verification fails
    """
    try:
        table = get_dynamodb_table(table_name, region)

        # Query by document_id using GSI
        response = table.query(
            IndexName="document_index",
            KeyConditionExpression="document_id = :doc_id",
            ExpressionAttributeValues={":doc_id": document_id},
        )

        if response["Count"] == 0:
            logger.warning(f"Document {document_id} not found in {table_name}")
            return False

        doc_item = response["Items"][0]

        if expected_collection_id and doc_item.get("collection_id") != expected_collection_id:
            logger.warning(
                f"Document {document_id} has collection_id {doc_item.get('collection_id')}, "
                f"expected {expected_collection_id}"
            )
            return False

        logger.info(f"Document {document_id} verified in {table_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to verify document in DynamoDB: {e}")
        raise


def verify_document_in_s3(s3_uri: str, region: str | None = None) -> bool:
    """Verify a document exists in S3.

    Args:
        s3_uri: S3 URI (s3://bucket/key)
        region: AWS region (optional, uses default if not provided)

    Returns:
        bool: True if document exists

    Raises:
        Exception: If verification fails
    """
    try:
        if not s3_uri.startswith("s3://"):
            logger.warning(f"Invalid S3 URI: {s3_uri}")
            return False

        s3_client = get_s3_client(region)
        bucket, key = s3_uri.replace("s3://", "").split("/", 1)

        s3_client.head_object(Bucket=bucket, Key=key)
        logger.info(f"Document verified in S3: {s3_uri}")
        return True

    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Document not found in S3: {s3_uri}")
        return False
    except Exception as e:
        logger.error(f"Failed to verify document in S3: {e}")
        raise


def verify_document_not_in_s3(s3_uri: str, region: str | None = None) -> bool:
    """Verify a document does NOT exist in S3.

    Args:
        s3_uri: S3 URI (s3://bucket/key)
        region: AWS region (optional, uses default if not provided)

    Returns:
        bool: True if document does not exist

    Raises:
        Exception: If verification fails
    """
    try:
        if not s3_uri.startswith("s3://"):
            logger.warning(f"Invalid S3 URI: {s3_uri}")
            return True

        s3_client = get_s3_client(region)
        bucket, key = s3_uri.replace("s3://", "").split("/", 1)

        s3_client.head_object(Bucket=bucket, Key=key)
        logger.warning(f"Document still exists in S3: {s3_uri}")
        return False

    except s3_client.exceptions.NoSuchKey:
        logger.info(f"Document confirmed deleted from S3: {s3_uri}")
        return True
    except Exception as e:
        logger.error(f"Failed to verify document deletion in S3: {e}")
        raise


def get_table_names_from_env(deployment_name: str) -> dict[str, str]:
    """Get DynamoDB table names from environment or construct from deployment name.

    Args:
        deployment_name: The LISA deployment name

    Returns:
        Dict[str, str]: Dictionary of table names
    """
    return {
        "collections": os.getenv("LISA_RAG_COLLECTIONS_TABLE", f"{deployment_name}-LisaRagCollectionsTable"),
        "documents": os.getenv("LISA_RAG_DOCUMENTS_TABLE", f"{deployment_name}-LisaRagDocumentsTable"),
        "subdocuments": os.getenv("LISA_RAG_SUBDOCUMENTS_TABLE", f"{deployment_name}-LisaRagSubDocumentsTable"),
    }
