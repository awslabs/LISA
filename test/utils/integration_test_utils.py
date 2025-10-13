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
- Authentication setup
- API client creation
- Resource management
- Waiting for resources to be ready
"""

import logging
import os
import sys
import time
from typing import Any, Callable, Dict, Optional

import boto3

# Add lisa-sdk to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lisa-sdk"))

from lisapy.api import LisaApi

logger = logging.getLogger(__name__)


def get_management_key(deployment_name: str, region: Optional[str] = None, deployment_stage: Optional[str] = None) -> str:
    """Retrieve management key from AWS Secrets Manager.

    Args:
        deployment_name: The LISA deployment name
        region: AWS region (optional, uses default if not provided)
        deployment_stage: The deployment stage (optional, will try multiple patterns if not provided)

    Returns:
        str: The management API key

    Raises:
        Exception: If the key cannot be retrieved
    """
    secrets_client = boto3.client("secretsmanager", region_name=region) if region else boto3.client("secretsmanager")
    
    # Try different secret name patterns
    secret_patterns = []
    if deployment_stage:
        secret_patterns.append(f"{deployment_stage}-{deployment_name}-management-key")
    secret_patterns.extend([
        f"{deployment_name}-lisa-management-key",
        f"{deployment_name}-management-key",
        f"lisa-{deployment_name}-management-key",
    ])
    
    last_error = None
    for secret_name in secret_patterns:
        try:
            response = secrets_client.get_secret_value(SecretId=secret_name)
            # Secret is stored as a plain string, not JSON
            api_key = response["SecretString"]
            logger.info(f"Retrieved management key from {secret_name}")
            return api_key
        except Exception as e:
            last_error = e
            logger.debug(f"Secret {secret_name} not found, trying next pattern...")
            continue
    
    # If we get here, none of the patterns worked
    logger.error(f"Failed to retrieve management key. Tried patterns: {secret_patterns}")
    logger.error(f"Last error: {last_error}")
    raise Exception(f"Could not find management key. Tried: {', '.join(secret_patterns)}")


def create_api_token(deployment_name: str, api_key: str, region: Optional[str] = None, ttl_seconds: int = 3600) -> str:
    """Create an API token in DynamoDB with expiration.

    Args:
        deployment_name: The LISA deployment name
        api_key: The management API key
        region: AWS region (optional, uses default if not provided)
        ttl_seconds: Time to live in seconds (default: 1 hour)

    Returns:
        str: The created API token

    Raises:
        Exception: If token creation fails
    """
    try:
        dynamodb = boto3.resource("dynamodb", region_name=region) if region else boto3.resource("dynamodb")
        table_name = f"{deployment_name}-LISAApiTokenTable"
        table = dynamodb.Table(table_name)

        # Create token with expiration
        current_time = int(time.time())
        expiration_time = current_time + ttl_seconds

        # Put item in DynamoDB
        item = {"token": api_key, "tokenExpiration": expiration_time}
        table.put_item(Item=item)

        logger.info(f"Created API token with expiration: {expiration_time}")
        return api_key

    except Exception as e:
        logger.error(f"Failed to create API token: {e}")
        raise


def setup_authentication(deployment_name: str, region: Optional[str] = None, deployment_stage: Optional[str] = None) -> Dict[str, str]:
    """Set up authentication for LISA API calls.

    Args:
        deployment_name: The LISA deployment name
        region: AWS region (optional, uses default if not provided)
        deployment_stage: The deployment stage (optional)

    Returns:
        Dict[str, str]: Authentication headers

    Raises:
        Exception: If authentication setup fails
    """
    logger.info(f"Setting up authentication for deployment: {deployment_name}")

    # Get management key from AWS Secrets Manager
    api_key = get_management_key(deployment_name, region, deployment_stage)

    # Create API token in DynamoDB (optional - for tracking purposes)
    try:
        create_api_token(deployment_name, api_key, region)
    except Exception as e:
        logger.warning(f"Failed to create DynamoDB token (proceeding anyway): {e}")

    # Return authentication headers
    headers = {"Api-Key": api_key, "Authorization": api_key}

    logger.info("Authentication setup completed")
    return headers


def create_lisa_client(
    api_url: str,
    deployment_name: str,
    region: Optional[str] = None,
    verify_ssl: bool = True,
    timeout: int = 10,
    deployment_stage: Optional[str] = None,
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

    # Setup authentication
    auth_headers = setup_authentication(deployment_name, region, deployment_stage)

    # Create client
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


def get_dynamodb_table(table_name: str, region: Optional[str] = None):
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


def get_s3_client(region: Optional[str] = None):
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
    expected_collection_id: Optional[str] = None,
    region: Optional[str] = None,
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
                f"Document {document_id} has collection_id {doc_item.get('collection_id')}, expected {expected_collection_id}"
            )
            return False

        logger.info(f"Document {document_id} verified in {table_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to verify document in DynamoDB: {e}")
        raise


def verify_document_in_s3(s3_uri: str, region: Optional[str] = None) -> bool:
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


def verify_document_not_in_s3(s3_uri: str, region: Optional[str] = None) -> bool:
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


def get_table_names_from_env(deployment_name: str) -> Dict[str, str]:
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
