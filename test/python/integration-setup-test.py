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
Integration test script that deploys resources to LISA.
This script creates:
- A Bedrock model
- A self-hosted model
- A PGVector repository
- An OpenSearch repository
- A Bedrock Knowledge Base with S3 data source
- A Bedrock Knowledge Base repository
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

import boto3

# Add lisa-sdk to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lisa-sdk"))

from lisapy.api import LisaApi
from lisapy.types import BedrockModelRequest, ModelRequest

DEFAULT_EMBEDDING_MODEL_ID = "e5-embed"
RAG_PIPELINE_BUCKET = "lisa-rag-pipeline"
BEDROCK_KB_S3_BUCKET = "bk-s3-test"


def get_management_key(deployment_name: str, deployment_stage: str) -> str:
    """Retrieve management key from AWS Secrets Manager.

    Args:
        deployment_name: The LISA deployment name

    Returns:
        str: The management API key
    """
    secret_name = f"{deployment_name}-management-key"
    print(f"  Looking for secret: {secret_name}")

    try:
        secrets_client = boto3.client("secretsmanager")
        response = secrets_client.get_secret_value(SecretId=secret_name)
        # Secret is stored as a plain string, not JSON
        api_key = response["SecretString"]
        return api_key
    except Exception as e:
        print(f"✗ Failed to retrieve management key from {secret_name}: {e}")
        raise


def create_api_token(deployment_name: str, api_key: str) -> str:
    """Create an API token in DynamoDB with expiration.

    Args:
        deployment_name: The LISA deployment name
        api_key: The management API key

    Returns:
        str: The created API token
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table_name = f"{deployment_name}-LISAApiTokenTable"
        table = dynamodb.Table(table_name)

        # Create token with 1 hour expiration (matching conftest.py)
        current_time = int(time.time())
        expiration_time = current_time + 3600  # 1 hour

        # Put item in DynamoDB (using same structure as conftest.py)
        item = {"token": api_key, "tokenExpiration": expiration_time}
        table.put_item(Item=item)

        print(f"✓ Created API token with expiration: {expiration_time}")
        return api_key  # Return the API key itself for authentication

    except Exception as e:
        print(f"✗ Failed to create API token: {e}")
        raise


def setup_authentication(deployment_name: str, deployment_stage: str) -> Dict[str, str]:
    """Set up authentication for LISA API calls.

    Args:
        deployment_name: The LISA deployment name

    Returns:
        Dict[str, str]: Authentication headers
    """
    print(f"🔑 Setting up authentication for deployment: {deployment_name}")

    # Get management key from AWS Secrets Manager
    api_key = get_management_key(deployment_name, deployment_stage)

    # Return authentication headers (same as conftest.py)
    headers = {"Api-Key": api_key, "Authorization": api_key}

    print("✓ Authentication setup completed")
    print(f"✓ Using API key: {api_key[:8]}...")  # Show first 8 chars for debugging
    return headers


def wait_for_resource_ready(
    lisa_client: LisaApi, resource_type: str, resource_id: str, check_func, max_wait_minutes: int = 30
) -> bool:
    """Wait for a resource to be ready/deployed.

    Args:
        lisa_client: LISA client instance
        resource_type: Type of resource (model, repository)
        resource_id: ID of the resource
        check_func: Function to check if resource is ready
        max_wait_minutes: Maximum minutes to wait

    Returns:
        bool: True if resource is ready, False if timeout
    """
    print(f"Waiting for {resource_type} '{resource_id}' to be ready...")

    max_iterations = max_wait_minutes * 4  # Check every 15 seconds
    for i in range(max_iterations):
        try:
            if check_func(resource_id):
                print(f"✓ {resource_type} '{resource_id}' is ready!")
                return True
        except Exception as e:
            print(f"  Check failed: {e}")

        if i < max_iterations - 1:
            print(f"  Still waiting... ({i+1}/{max_iterations})")
            time.sleep(15)

    print(f"✗ Timeout waiting for {resource_type} '{resource_id}' to be ready")
    return False


def check_model_ready(lisa_client: LisaApi, model_id: str) -> bool:
    """Check if a model is ready (InService status)."""
    try:
        model = lisa_client.get_model(model_id)
        status = model.get("status", "Unknown")
        print(f"    Model status: {status}")
        return status == "InService"
    except Exception:
        return False


def check_repository_ready(lisa_client: LisaApi, repository_id: str) -> bool:
    """Check if a repository is ready by checking status."""
    try:
        status = lisa_client.get_repository_status()
        repo_status = status.get(repository_id, "Unknown")
        print(f"    Repository status: {repo_status}")
        # Repository is ready when it's not in Creating or Failed state
        return repo_status not in ["Creating", "Failed", "Unknown"]
    except Exception:
        return False


def model_exists(lisa_client: LisaApi, model_id: str) -> bool:
    """Check if a model already exists."""
    try:
        lisa_client.get_model(model_id)
        return True
    except Exception:
        return False


def repository_exists(lisa_client: LisaApi, repository_id: str) -> bool:
    """Check if a repository already exists."""
    try:
        repositories = lisa_client.list_repositories()
        print(f"  DEBUG: list_repositories() returned {len(repositories)} repositories")
        for repo in repositories:
            if repo.get("repositoryId") == repository_id:
                return True
        return False
    except Exception as e:
        print(f"  DEBUG: list_repositories() raised exception: {type(e).__name__}: {e}")
        return False


def create_bedrock_model(
    lisa_client: LisaApi,
    model_id: str,
    model_name: str,
    model_type: str = "textgen",
    features: any = None,
    skip_create: bool = False,
) -> Dict[str, Any]:
    """Create a Bedrock model configuration."""

    # Skip creation if flag is set
    if skip_create:
        print(f"\n⏭️  Skipping creation of Bedrock model '{model_id}' (skip_create=True)")
        return {"modelId": model_id}

    # Check if model already exists
    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Bedrock model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}

    if features is None:
        features = [{"name": "summarization", "overview": ""}, {"name": "imageInput", "overview": ""}]

    print(f"\n🚀 Creating Bedrock model '{model_id}'...")

    bedrock_model_request: BedrockModelRequest = {
        "autoScalingConfig": None,
        "containerConfig": None,
        "inferenceContainer": None,
        "instanceType": None,
        "loadBalancerConfig": None,
        "modelId": model_id,
        "modelName": model_name,
        "modelDescription": "",
        "modelType": model_type,
        "modelUrl": "",
        "streaming": True if model_type != "embedding" else False,
        "features": features,
        "allowedGroups": None,
    }

    try:
        result = lisa_client.create_bedrock_model(bedrock_model_request)
        print(f"✓ Bedrock model created: {result}")

        # Handle case where response doesn't contain modelId
        if result is None or not isinstance(result, dict):
            result = {"modelId": bedrock_model_request["modelId"]}
        elif "modelId" not in result:
            result["modelId"] = bedrock_model_request["modelId"]

        return result
    except Exception as e:
        print(f"✗ Failed to create Bedrock model: {e}")
        raise


def create_self_hosted_embedded_model(
    lisa_client: LisaApi,
    model_id: str,
    model_name: str,
    base_image: str = "ghcr.io/huggingface/text-embeddings-inference:latest",
    skip_create: bool = False,
) -> Dict[str, Any]:
    """Create a self-hosted embedded model configuration."""

    # Skip creation if flag is set
    if skip_create:
        print(f"\n⏭️  Skipping creation of self-hosted embedded model '{model_id}' (skip_create=True)")
        return {"modelId": model_id}

    # Check if model already exists
    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Self-hosted embedded model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}

    print(f"\n🚀 Creating self-hosted embedded model '{model_id}'...")

    self_hosted_embedded_model_request: ModelRequest = {
        "autoScalingConfig": {
            "blockDeviceVolumeSize": 50,
            "minCapacity": 1,
            "maxCapacity": 1,
            "cooldown": 420,
            "defaultInstanceWarmup": 300,  # Embedding models load faster
            "metricConfig": {
                "albMetricName": "RequestCountPerTarget",
                "targetValue": 30,
                "duration": 60,
                "estimatedInstanceWarmup": 300,
            },
        },
        "containerConfig": {
            "image": {"baseImage": base_image, "type": "asset"},
            "sharedMemorySize": 2048,
            "healthCheckConfig": {
                "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                "interval": 10,
                "startPeriod": 300,  # 10 minutes to allow for model loading
                "timeout": 5,
                "retries": 3,
            },
            "environment": {
                "MAX_TOTAL_TOKENS": "16384",
                "MAX_INPUT_LENGTH": "8192",
                "MAX_BATCH_TOKENS": "4096",
                "MAX_CONCURRENT_REQUESTS": "512",
                "MAX_CLIENT_BATCH_SIZE": "1024",
                "POOLING": "mean",
                "AUTO_TRUNCATE": "true",
            },
        },
        "inferenceContainer": "tei",
        "instanceType": "g5.xlarge",
        "loadBalancerConfig": {
            "healthCheckConfig": {
                "path": "/health",
                "interval": 60,
                "timeout": 30,
                "healthyThresholdCount": 2,
                "unhealthyThresholdCount": 10,
            }
        },
        "modelId": model_id,
        "modelName": model_name,
        "modelDescription": f"Testing model for {model_name}",
        "modelType": "embedding",
        "streaming": False,
        "features": [],
        "allowedGroups": None,
    }

    try:
        result = lisa_client.create_self_hosted_embedded_model(self_hosted_embedded_model_request)
        print(f"✓ Self-hosted embedded model created: {result}")

        # Handle case where response doesn't contain modelId
        if result is None or not isinstance(result, dict):
            result = {"modelId": self_hosted_embedded_model_request["modelId"]}
        elif "modelId" not in result:
            result["modelId"] = self_hosted_embedded_model_request["modelId"]

        return result
    except Exception as e:
        print(f"✗ Failed to create self-hosted embedded model: {e}")
        raise


def create_self_hosted_model(
    lisa_client: LisaApi,
    model_id: str,
    model_name: str,
    base_image: str = "vllm/vllm-openai:latest",
    skip_create: bool = False,
) -> Dict[str, Any]:
    """Create a self-hosted model configuration."""

    # Skip creation if flag is set
    if skip_create:
        print(f"\n⏭️  Skipping creation of self-hosted model '{model_id}' (skip_create=True)")
        return {"modelId": model_id}

    # Check if model already exists
    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Self-hosted model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}

    print(f"\n🚀 Creating self-hosted model '{model_id}'...")

    # Get available instances
    instances = lisa_client.list_instances()
    if not instances:
        raise Exception("No EC2 instances available for self-hosted model")

    # Use the first available instance type that supports GPU workloads
    gpu_instances = [inst for inst in instances if "g5" in inst.lower() or "p3" in inst.lower() or "p4" in inst.lower()]
    instance_type = gpu_instances[0] if gpu_instances else instances[0]
    print(f"  Using instance type: {instance_type}")
    self_hosted_model_request: ModelRequest = {
        "autoScalingConfig": {
            "blockDeviceVolumeSize": 50,
            "minCapacity": 1,
            "maxCapacity": 1,
            "cooldown": 420,
            "defaultInstanceWarmup": 300,  # Match model loading time
            "metricConfig": {
                "albMetricName": "RequestCountPerTarget",
                "targetValue": 30,
                "duration": 60,
                "estimatedInstanceWarmup": 300,  # Match model loading time
            },
        },
        "containerConfig": {
            "image": {"baseImage": base_image, "type": "asset"},
            "sharedMemorySize": 2048,
            "healthCheckConfig": {
                "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                "interval": 10,
                "startPeriod": 300,  # 10 minutes to allow for model loading
                "timeout": 5,
                "retries": 3,
            },
            "environment": {
                # MAX_TOTAL_TOKENS is mapped to VLLM_MAX_MODEL_LEN in entrypoint.sh
                "MAX_TOTAL_TOKENS": "16384",
                "MAX_INPUT_LENGTH": "8192",
                "MAX_BATCH_TOKENS": "4096",
                "MAX_CONCURRENT_REQUESTS": "128",
            },
        },
        "inferenceContainer": "vllm",
        "instanceType": "g5.xlarge",
        "loadBalancerConfig": {
            "healthCheckConfig": {
                "path": "/health",
                "interval": 60,
                "timeout": 30,
                "healthyThresholdCount": 2,
                "unhealthyThresholdCount": 10,
            }
        },
        "modelId": model_id,
        "modelName": model_name,
        "modelDescription": None,
        "modelType": "textgen",
        "streaming": True,
        "features": [{"name": "summarization", "overview": ""}, {"name": "imageInput", "overview": ""}],
        "allowedGroups": None,
    }

    try:
        result = lisa_client.create_self_hosted_model(self_hosted_model_request)
        print(f"✓ Self-hosted model created: {result}")

        # Handle case where response doesn't contain modelId
        if result is None or not isinstance(result, dict):
            result = {"modelId": self_hosted_model_request["modelId"]}
        elif "modelId" not in result:
            result["modelId"] = self_hosted_model_request["modelId"]

        return result
    except Exception as e:
        print(f"✗ Failed to create self-hosted model: {e}")
        raise


def create_pgvector_repository(
    lisa_client: LisaApi, embedding_model_id: str = None, skip_create: bool = False
) -> Dict[str, Any]:
    """Create a PGVector repository."""
    repository_id = "pgv-rag"

    # Skip creation if flag is set
    if skip_create:
        print(f"\n⏭️  Skipping creation of PGVector repository '{repository_id}' (skip_create=True)")
        return {"repositoryId": repository_id}

    # Check if repository already exists
    if repository_exists(lisa_client, repository_id):
        print(f"\n⏭️  PGVector repository '{repository_id}' already exists, skipping creation")
        return {"repositoryId": repository_id}

    print(f"\n🚀 Creating PGVector repository '{repository_id}'...")

    try:
        rag_config = {
            "pipelines": [
                {
                    "s3Prefix": "",
                    "trigger": "event",
                    "autoRemove": True,
                    "metadata": {"tags": ["test"]},
                    "chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 51},
                    "collectionId": "default",
                    "s3Bucket": RAG_PIPELINE_BUCKET,
                }
            ],
            "allowedGroups": [],
            "repositoryId": repository_id,
            "embeddingModelId": embedding_model_id or DEFAULT_EMBEDDING_MODEL_ID,
            "rdsConfig": {"username": "postgres", "dbName": "postgres", "dbPort": 5432},
            "type": "pgvector",
        }

        result = lisa_client.create_pgvector_repository(rag_config)
        print(f"✓ PGVector repository created: {result}")

        # Handle case where response doesn't contain repositoryId
        if result is None or not isinstance(result, dict):
            result = {"repositoryId": rag_config["repositoryId"]}
        elif "repositoryId" not in result:
            result["repositoryId"] = rag_config["repositoryId"]

        return result
    except Exception as e:
        print(f"✗ Failed to create PGVector repository: {e}")
        raise


def create_opensearch_repository(
    lisa_client: LisaApi, embedding_model_id: str = None, skip_create: bool = False
) -> Dict[str, Any]:
    """Create an OpenSearch repository."""
    repository_id = "os-rag"

    # Skip creation if flag is set
    if skip_create:
        print(f"\n⏭️  Skipping creation of OpenSearch repository '{repository_id}' (skip_create=True)")
        return {"repositoryId": repository_id}

    # Check if repository already exists
    if repository_exists(lisa_client, repository_id):
        print(f"\n⏭️  OpenSearch repository '{repository_id}' already exists, skipping creation")
        return {"repositoryId": repository_id}

    print(f"\n🚀 Creating OpenSearch repository '{repository_id}'...")

    try:
        rag_config = {
            "repositoryId": repository_id,
            "embeddingModelId": embedding_model_id or DEFAULT_EMBEDDING_MODEL_ID,
            "type": "opensearch",
            "allowedGroups": [],
            "pipelines": [
                {
                    "s3Prefix": "",
                    "trigger": "event",
                    "autoRemove": True,
                    "metadata": {"tags": ["test"]},
                    "chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 51},
                    "collectionId": "default",
                    "s3Bucket": RAG_PIPELINE_BUCKET,
                }
            ],
            "opensearchConfig": {
                "dataNodes": 2,
                "dataNodeInstanceType": "r7g.large.search",
                "masterNodes": 0,
                "masterNodeInstanceType": "r7g.large.search",
                "volumeSize": 20,
                "volumeType": "gp3",
                "multiAzWithStandby": False,
            },
        }
        result = lisa_client.create_repository(rag_config)
        print(f"✓ OpenSearch repository created: {result}")

        # Handle case where response doesn't contain repositoryId
        if result is None or not isinstance(result, dict):
            result = {"repositoryId": rag_config["repositoryId"]}
        elif "repositoryId" not in result:
            result["repositoryId"] = rag_config["repositoryId"]

        return result
    except Exception as e:
        print(f"✗ Failed to create OpenSearch repository: {e}")
        raise


def create_bedrock_kb_repository(
    lisa_client: LisaApi,
    knowledge_base_id: str,
    data_source_id: str,
    data_source_name: str,
    s3_bucket: str,
    embedding_model_id: str = None,
    skip_create: bool = False,
) -> Dict[str, Any]:
    """Create a Bedrock Knowledge Base repository using LISA SDK.

    Args:
        lisa_client: LISA API client
        knowledge_base_id: The Bedrock Knowledge Base ID to connect to
        data_source_id: The data source ID within the Knowledge Base
        data_source_name: The name of the data source
        s3_bucket: The S3 bucket used by the data source
        embedding_model_id: Optional embedding model ID
        skip_create: Skip creation if True

    Returns:
        Dict containing repositoryId
    """
    repository_id = "bedrock-kb-rag"

    # Skip creation if flag is set
    if skip_create:
        print(f"\n⏭️  Skipping creation of Bedrock KB repository '{repository_id}' (skip_create=True)")
        return {"repositoryId": repository_id}

    # Check if repository already exists
    if repository_exists(lisa_client, repository_id):
        print(f"\n⏭️  Bedrock KB repository '{repository_id}' already exists, skipping creation")
        return {"repositoryId": repository_id}

    print(f"\n🚀 Creating Bedrock KB repository '{repository_id}' for Knowledge Base '{knowledge_base_id}'...")

    try:
        rag_config = {
            "repositoryId": repository_id,
            "embeddingModelId": embedding_model_id or DEFAULT_EMBEDDING_MODEL_ID,
            "type": "bedrock_knowledge_base",
            "allowedGroups": [],
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": knowledge_base_id,
                "dataSources": [
                    {
                        "id": data_source_id,
                        "name": data_source_name,
                        "s3Uri": f"s3://{s3_bucket}/",
                    }
                ],
            },
        }

        result = lisa_client.create_bedrock_kb_repository(rag_config)
        print(f"✓ Bedrock KB repository created: {result}")

        # Handle case where response doesn't contain repositoryId
        if result is None or not isinstance(result, dict):
            result = {"repositoryId": rag_config["repositoryId"]}
        elif "repositoryId" not in result:
            result["repositoryId"] = rag_config["repositoryId"]

        return result
    except Exception as e:
        print(f"✗ Failed to create Bedrock KB repository: {e}")
        raise


def create_bedrock_knowledge_base(
    deployment_name: str,
    region: str,
    kb_name: str = "bedrock-kb-e2e-test",
    s3_bucket_name: str = BEDROCK_KB_S3_BUCKET,
    embedding_model_arn: str = None,
    skip_create: bool = False,
) -> Dict[str, Any]:
    """Create a Bedrock Knowledge Base with S3 data source.

    Args:
        deployment_name: The LISA deployment name
        region: AWS region
        kb_name: Name for the knowledge base
        s3_bucket_name: Name of the S3 bucket to create and use as data source
        embedding_model_arn: ARN of the embedding model (defaults to Titan Embed)
        skip_create: Skip creation if True

    Returns:
        Dict containing knowledgeBaseId, dataSourceId, and s3Bucket
    """
    if skip_create:
        print(f"\n⏭️  Skipping creation of Bedrock Knowledge Base '{kb_name}' (skip_create=True)")
        return {"knowledgeBaseId": f"{kb_name}-id", "dataSourceId": f"{kb_name}-ds-id"}

    print(f"\n🚀 Setting up Bedrock Knowledge Base '{kb_name}'...")

    try:
        s3_client = boto3.client("s3", region_name=region)
        sts_client = boto3.client("sts", region_name=region)
        iam_client = boto3.client("iam", region_name=region)
        aoss_client = boto3.client("opensearchserverless", region_name=region)
        bedrock_agent_client = boto3.client("bedrock-agent", region_name=region)

        # Get account ID
        account_id = sts_client.get_caller_identity()["Account"]

        # 1. Check if S3 bucket exists, create only if it doesn't
        bucket_name = f"{deployment_name}-{s3_bucket_name}"
        print(f"  Checking S3 bucket: {bucket_name}")

        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✓ S3 bucket already exists: {bucket_name}")
        except s3_client.exceptions.NoSuchBucket:
            print(f"  Creating S3 bucket: {bucket_name}")
            try:
                if region == "us-east-1":
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
                    )
                print(f"✓ S3 bucket created: {bucket_name}")
            except Exception as e:
                print(f"⚠️  S3 bucket creation issue: {e}")
        except Exception as e:
            print(f"⚠️  S3 bucket check issue: {e}")

        # 2. Create IAM role for Bedrock Knowledge Base
        role_name = f"{deployment_name}-BedrockKBRole"
        print(f"  Creating IAM role: {role_name}")

        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        try:
            role_response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Role for Bedrock Knowledge Base - {deployment_name}",
            )
            role_arn = role_response["Role"]["Arn"]
            print(f"✓ IAM role created: {role_arn}")

            # Attach necessary policies
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:ListBucket"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}", f"arn:aws:s3:::{bucket_name}/*"],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["bedrock:InvokeModel"],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["aoss:APIAccessAll"],
                        "Resource": "*",
                    },
                ],
            }

            iam_client.put_role_policy(
                RoleName=role_name, PolicyName=f"{role_name}-Policy", PolicyDocument=json.dumps(policy_document)
            )
            print("✓ IAM policy attached to role")

            # Wait for role to propagate
            time.sleep(10)

        except iam_client.exceptions.EntityAlreadyExistsException:
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
            print(f"✓ IAM role already exists: {role_arn}")

        # 3. Create OpenSearch Serverless collection
        collection_name = f"{deployment_name}-kb-collection"
        print(f"  Creating OpenSearch Serverless collection: {collection_name}")

        try:
            # First, create encryption security policy
            encryption_policy_name = f"{deployment_name}-kb-encryption"
            encryption_policy = {
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{collection_name}"],
                    }
                ],
                "AWSOwnedKey": True,
            }

            try:
                aoss_client.create_security_policy(
                    name=encryption_policy_name,
                    type="encryption",
                    policy=json.dumps(encryption_policy),
                    description=f"Encryption policy for {collection_name}",
                )
                print(f"✓ Created encryption security policy: {encryption_policy_name}")
            except aoss_client.exceptions.ConflictException:
                print(f"✓ Encryption security policy already exists: {encryption_policy_name}")

            # Create network security policy (allow public access for testing)
            network_policy_name = f"{deployment_name}-kb-network"
            network_policy = [
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                        }
                    ],
                    "AllowFromPublic": True,
                }
            ]

            try:
                aoss_client.create_security_policy(
                    name=network_policy_name,
                    type="network",
                    policy=json.dumps(network_policy),
                    description=f"Network policy for {collection_name}",
                )
                print(f"✓ Created network security policy: {network_policy_name}")
            except aoss_client.exceptions.ConflictException:
                print(f"✓ Network security policy already exists: {network_policy_name}")

            # Create data access policy
            data_policy_name = f"{deployment_name}-kb-data-access"
            data_policy = [
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:DeleteCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems",
                            ],
                        },
                        {
                            "ResourceType": "index",
                            "Resource": [f"index/{collection_name}/*"],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DeleteIndex",
                                "aoss:UpdateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                            ],
                        },
                    ],
                    "Principal": [role_arn, f"arn:aws:iam::{account_id}:root"],
                }
            ]

            try:
                aoss_client.create_access_policy(
                    name=data_policy_name,
                    type="data",
                    policy=json.dumps(data_policy),
                    description=f"Data access policy for {collection_name}",
                )
                print(f"✓ Created data access policy: {data_policy_name}")
            except aoss_client.exceptions.ConflictException:
                print(f"✓ Data access policy already exists: {data_policy_name}")

            # Now create the collection
            collection_response = aoss_client.create_collection(
                name=collection_name, type="VECTORSEARCH", description=f"Collection for {kb_name}"
            )
            collection_id = collection_response["createCollectionDetail"]["id"]
            collection_arn = collection_response["createCollectionDetail"]["arn"]
            print(f"✓ OpenSearch Serverless collection created: {collection_id}")

            # Wait for collection to be active
            print("  Waiting for collection to be active...")
            max_wait = 60  # 5 minutes
            for i in range(max_wait):
                collection_status = aoss_client.batch_get_collection(ids=[collection_id])
                if collection_status["collectionDetails"][0]["status"] == "ACTIVE":
                    print("✓ Collection is active")
                    break
                time.sleep(5)

        except Exception as e:
            print(f"⚠️  OpenSearch Serverless collection issue: {e}")
            # Try to find existing collection
            collections = aoss_client.list_collections(collectionFilters={"name": collection_name})
            if collections["collectionSummaries"]:
                collection_id = collections["collectionSummaries"][0]["id"]
                collection_arn = collections["collectionSummaries"][0]["arn"]
                print(f"✓ Using existing collection: {collection_id}")
            else:
                raise

        # Create the vector index in OpenSearch Serverless if it doesn't exist
        index_name = f"{kb_name}-index"
        print(f"  Creating vector index '{index_name}' in collection...")

        try:
            # Get the collection endpoint
            collection_details = aoss_client.batch_get_collection(ids=[collection_id])
            collection_endpoint = collection_details["collectionDetails"][0]["collectionEndpoint"]

            # Remove https:// prefix if present
            if collection_endpoint.startswith("https://"):
                collection_endpoint = collection_endpoint[8:]

            # Create OpenSearch client for the collection
            from opensearchpy import OpenSearch, RequestsHttpConnection
            from requests_aws4auth import AWS4Auth

            credentials = boto3.Session().get_credentials()
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                "aoss",
                session_token=credentials.token,
            )

            os_client = OpenSearch(
                hosts=[{"host": collection_endpoint, "port": 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=30,
            )

            # Check if index exists
            if not os_client.indices.exists(index=index_name):
                # Create index with vector field mapping
                index_body = {
                    "settings": {"index.knn": True},
                    "mappings": {
                        "properties": {
                            "embedding": {
                                "type": "knn_vector",
                                "dimension": 1024,  # Titan Embed v2 dimension
                                "method": {
                                    "name": "hnsw",
                                    "engine": "faiss",
                                    "parameters": {"ef_construction": 512, "m": 16},
                                },
                            },
                            "text": {"type": "text"},
                            "metadata": {"type": "text"},
                        }
                    },
                }

                os_client.indices.create(index=index_name, body=index_body)
                print(f"✓ Created vector index: {index_name}")
            else:
                print(f"✓ Vector index already exists: {index_name}")

        except ImportError:
            print("⚠️  opensearch-py not installed, skipping index creation")
            print("    Install with: pip install opensearch-py requests-aws4auth")
        except Exception as e:
            print(f"⚠️  Could not create vector index: {e}")
            print("    The Knowledge Base creation may fail if the index doesn't exist")

        # 4. Set default embedding model if not provided
        if not embedding_model_arn:
            embedding_model_arn = f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"

        # 5. Check if Knowledge Base already exists
        print(f"  Checking if Knowledge Base '{kb_name}' exists...")
        existing_kb_id = None
        existing_ds_id = None

        try:
            # List all knowledge bases and check if one with our name exists
            kb_list = bedrock_agent_client.list_knowledge_bases()
            for kb in kb_list.get("knowledgeBaseSummaries", []):
                if kb.get("name") == kb_name:
                    existing_kb_id = kb.get("knowledgeBaseId")
                    print(f"✓ Knowledge Base already exists: {existing_kb_id}")

                    # Get data sources for this KB
                    ds_list = bedrock_agent_client.list_data_sources(knowledgeBaseId=existing_kb_id)
                    if ds_list.get("dataSourceSummaries"):
                        existing_ds_id = ds_list["dataSourceSummaries"][0]["dataSourceId"]
                        print(f"✓ Data source already exists: {existing_ds_id}")
                    break
        except Exception as e:
            print(f"  Could not check existing knowledge bases: {e}")

        # If KB exists, return existing info
        if existing_kb_id:
            result = {
                "knowledgeBaseId": existing_kb_id,
                "dataSourceId": existing_ds_id,
                "s3Bucket": bucket_name,
                "collectionId": collection_id,
                "roleArn": role_arn,
            }
            print("✓ Using existing Bedrock Knowledge Base")
            return result

        # 6. Create Knowledge Base with OpenSearch Serverless
        print(f"  Creating Knowledge Base with OpenSearch Serverless and embedding model: {embedding_model_arn}")

        kb_response = bedrock_agent_client.create_knowledge_base(
            name=kb_name,
            description=f"Test Knowledge Base for LISA integration testing - {deployment_name}",
            roleArn=role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": embedding_model_arn,
                },
            },
            storageConfiguration={
                "type": "OPENSEARCH_SERVERLESS",
                "opensearchServerlessConfiguration": {
                    "collectionArn": collection_arn,
                    "vectorIndexName": f"{kb_name}-index",
                    "fieldMapping": {
                        "vectorField": "embedding",
                        "textField": "text",
                        "metadataField": "metadata",
                    },
                },
            },
        )

        knowledge_base_id = kb_response["knowledgeBase"]["knowledgeBaseId"]
        print(f"✓ Knowledge Base created: {knowledge_base_id}")

        # 7. Create S3 Data Source
        print(f"  Creating S3 data source for bucket: {bucket_name}")

        ds_response = bedrock_agent_client.create_data_source(
            knowledgeBaseId=knowledge_base_id,
            name=f"{kb_name}-s3-source",
            description=f"S3 data source for {kb_name}",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{bucket_name}",
                    "inclusionPrefixes": ["documents/"],
                },
            },
        )

        data_source_id = ds_response["dataSource"]["dataSourceId"]
        print(f"✓ Data source created: {data_source_id}")

        result = {
            "knowledgeBaseId": knowledge_base_id,
            "dataSourceId": data_source_id,
            "s3Bucket": bucket_name,
            "collectionId": collection_id,
            "roleArn": role_arn,
        }

        print(f"✓ Bedrock Knowledge Base setup complete: {result}")
        return result

    except Exception as e:
        print(f"✗ Failed to create Bedrock Knowledge Base: {e}")
        import traceback

        traceback.print_exc()
        raise


def cleanup_resources(lisa_client: LisaApi, created_resources: Dict[str, list]):
    """Clean up created resources."""
    print("\n🧹 Cleaning up created resources...")

    # Clean up models
    for model_id in created_resources.get("models", []):
        try:
            lisa_client.delete_model(model_id)
            print(f"✓ Deleted model: {model_id}")
        except Exception as e:
            print(f"✗ Failed to delete model {model_id}: {e}")

    # Clean up repositories
    for repo_id in created_resources.get("repositories", []):
        try:
            lisa_client.delete_repository(repo_id)
            print(f"✓ Deleted repository: {repo_id}")
        except Exception as e:
            print(f"✗ Failed to delete repository {repo_id}: {e}")

    # Clean up Bedrock Knowledge Bases
    for kb_info in created_resources.get("knowledge_bases", []):
        try:
            bedrock_agent_client = boto3.client("bedrock-agent")
            s3_client = boto3.client("s3")

            kb_id = kb_info.get("knowledgeBaseId")
            s3_bucket = kb_info.get("s3Bucket")

            # Delete data source first
            if "dataSourceId" in kb_info:
                try:
                    bedrock_agent_client.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=kb_info["dataSourceId"])
                    print(f"✓ Deleted data source: {kb_info['dataSourceId']}")
                except Exception as e:
                    print(f"✗ Failed to delete data source {kb_info['dataSourceId']}: {e}")

            # Delete knowledge base
            try:
                bedrock_agent_client.delete_knowledge_base(knowledgeBaseId=kb_id)
                print(f"✓ Deleted knowledge base: {kb_id}")
            except Exception as e:
                print(f"✗ Failed to delete knowledge base {kb_id}: {e}")

            # Delete S3 bucket (empty it first)
            if s3_bucket:
                try:
                    # Delete all objects in bucket
                    paginator = s3_client.get_paginator("list_objects_v2")
                    for page in paginator.paginate(Bucket=s3_bucket):
                        if "Contents" in page:
                            objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                            s3_client.delete_objects(Bucket=s3_bucket, Delete={"Objects": objects})

                    # Delete bucket
                    s3_client.delete_bucket(Bucket=s3_bucket)
                    print(f"✓ Deleted S3 bucket: {s3_bucket}")
                except Exception as e:
                    print(f"✗ Failed to delete S3 bucket {s3_bucket}: {e}")

        except Exception as e:
            print(f"✗ Failed to delete knowledge base {kb_info}: {e}")


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="LISA Integration Setup Test")
    parser.add_argument("--url", required=True, help="LISA ALB URL")
    parser.add_argument("--api", required=True, help="LISA API URL")
    parser.add_argument("--deployment-name", required=True, help="LISA deployment name for authentication")
    parser.add_argument("--deployment-stage", required=True, help="LISA deployment stage for authentication")
    parser.add_argument("--deployment-prefix", required=True, help="LISA deployment prefix")
    parser.add_argument("--verify", default="false", help="Verify SSL certificates")
    parser.add_argument("--profile", help="AWS profile to use")
    parser.add_argument("--cleanup", action="store_true", help="Clean up resources (delete models and repositories)")
    parser.add_argument(
        "--skip-create", action="store_true", help="Skip resource creation, only collect resource IDs for cleanup"
    )
    parser.add_argument("--wait", action="store_true", help="Wait for resources to be ready")

    args = parser.parse_args()

    # Convert verify to boolean
    verify_ssl = args.verify.lower() not in ["false", "0", "no", "off"]
    print("🚀 LISA Integration Setup Test Starting...")
    print(f"ALB URL: {args.url}")
    print(f"API URL: {args.api}")
    print(f"Deployment Name: {args.deployment_name}")
    print(f"Deployment Stage: {args.deployment_stage}")
    print(f"Deployment Prefix: {args.deployment_prefix}")
    print(f"Verify SSL: {verify_ssl}")
    print(f"AWS Profile: {args.profile}")

    try:
        # Setup authentication

        auth_headers = setup_authentication(args.deployment_name, args.deployment_stage)

        # Initialize LISA client with authentication
        lisa_client = LisaApi(url=args.api, verify=verify_ssl, headers=auth_headers)

        created_resources = {"models": [], "repositories": [], "knowledge_bases": []}

        # If cleanup-only mode, skip all creation and just populate resource IDs
        if args.cleanup and args.skip_create:
            print("\n🧹 Cleanup-only mode: Collecting resource IDs for deletion...")

            # Define all resource IDs that would be created
            created_resources["models"] = [
                "nova-lite",
                "nova-canvas",
                "haiku-45",
                "sonnet-45",
                "titan-embed",
                "mistral-7b-instruct-03",
                "llama-32-1b-instruct",
                "gpt-oss-20b",
                DEFAULT_EMBEDDING_MODEL_ID,
                "qwen3-embed-06b",
                "baai-embed-15",
            ]
            created_resources["repositories"] = [
                "pgv-rag",
                "os-rag",
                "bedrock-kb-rag",
            ]
            created_resources["knowledge_bases"] = [
                {
                    "knowledgeBaseId": "bedrock-kb-e2e-test-id",
                    "dataSourceId": "bedrock-kb-e2e-test-ds-id",
                    "s3Bucket": f"{args.deployment_name}-{BEDROCK_KB_S3_BUCKET}",
                }
            ]

            print(f"  Models to delete: {created_resources['models']}")
            print(f"  Repositories to delete: {created_resources['repositories']}")

            # Skip to cleanup
            cleanup_resources(lisa_client, created_resources)
            print("\n🧹 Cleanup completed!")
            print("\n✅ Integration setup test completed successfully!")
            return 0

        # Get an embedding model for repositories
        embedding_models = lisa_client.list_embedding_models()
        embedding_model_id = None
        if embedding_models:
            embedding_model_id = embedding_models[0].get("modelId")
            print(f"Using embedding model: {embedding_model_id}")
        else:
            print("⚠️  No embedding models found, repositories will be created without default embedding model")

        models = []
        # 1. Create Bedrock models
        models.extend(
            [
                create_bedrock_model(
                    lisa_client, "nova-lite", "bedrock/us.amazon.nova-lite-v1:0", skip_create=args.skip_create
                ),
                create_bedrock_model(
                    lisa_client,
                    "haiku-45",
                    "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0",
                    skip_create=args.skip_create,
                ),
                create_bedrock_model(
                    lisa_client,
                    "sonnet-45",
                    "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    skip_create=args.skip_create,
                ),
                create_bedrock_model(
                    lisa_client,
                    "titan-embed",
                    "bedrock/amazon.titan-embed-text-v2:0",
                    "embedding",
                    [],
                    args.skip_create,
                ),
                create_bedrock_model(
                    lisa_client,
                    "nova-canvas",
                    "bedrock/amazon.nova-canvas-v1:0",
                    "imagegen",
                    [],
                    skip_create=args.skip_create,
                ),
            ]
        )

        # 2. Create self-hosted model
        models.extend(
            [
                create_self_hosted_model(
                    lisa_client,
                    "mistral-7b-instruct-03",
                    "mistralai/Mistral-7B-Instruct-v0.3",
                    skip_create=args.skip_create,
                ),
                create_self_hosted_model(
                    lisa_client,
                    "llama-32-1b-instruct",
                    "meta-llama/Llama-3.2-1B-Instruct",
                    skip_create=args.skip_create,
                ),
                create_self_hosted_model(
                    lisa_client, "gpt-oss-20b", "openai/gpt-oss-20b", skip_create=args.skip_create
                ),
            ]
        )

        # 3. Create self-hosted embedded model
        models.extend(
            [
                create_self_hosted_embedded_model(
                    lisa_client, DEFAULT_EMBEDDING_MODEL_ID, "intfloat/e5-large-v2", skip_create=args.skip_create
                ),
                create_self_hosted_embedded_model(
                    lisa_client, "qwen3-embed-06b", "Qwen/Qwen3-Embedding-0.6B", skip_create=args.skip_create
                ),
                create_self_hosted_embedded_model(
                    lisa_client, "baai-embed-15", "BAAI/bge-large-en-v1.5", skip_create=args.skip_create
                ),
            ]
        )

        for model in models:
            created_resources["models"].append(model["modelId"])

        repos = []
        repos.extend(
            [
                # # 4. Create PGVector repository
                create_pgvector_repository(lisa_client, embedding_model_id, skip_create=args.skip_create),
                # # 5. Create OpenSearch repository
                create_opensearch_repository(lisa_client, embedding_model_id, skip_create=args.skip_create),
            ]
        )

        for repo in repos:
            created_resources["repositories"].append(repo["repositoryId"])

        # 6. Create Bedrock Knowledge Base with S3 data source
        kb_result = create_bedrock_knowledge_base(
            deployment_name=args.deployment_name,
            region=os.environ.get("AWS_REGION", "us-east-1"),
            kb_name="bedrock-kb-e2e-test",
            skip_create=args.skip_create,
        )
        created_resources["knowledge_bases"].append(kb_result)

        # 7. Create Bedrock KB repository using the Knowledge Base
        if kb_result.get("knowledgeBaseId") and kb_result.get("dataSourceId"):
            bedrock_kb_repo = create_bedrock_kb_repository(
                lisa_client=lisa_client,
                knowledge_base_id=kb_result["knowledgeBaseId"],
                data_source_id=kb_result["dataSourceId"],
                data_source_name="bedrock-kb-e2e-test-s3-source",
                s3_bucket=kb_result["s3Bucket"],
                embedding_model_id=embedding_model_id,
                skip_create=args.skip_create,
            )
            created_resources["repositories"].append(bedrock_kb_repo["repositoryId"])

        if not args.skip_create:
            print("\n✅ All resources created successfully!")
        else:
            print("\n✅ Resource IDs collected successfully!")
        print("Resources:")
        print(f"  Models: {created_resources['models']}")
        print(f"  Repositories: {created_resources['repositories']}")
        print(f"  Knowledge Bases: {[kb.get('knowledgeBaseId') for kb in created_resources['knowledge_bases']]}")

        # Wait for resources to be ready if requested
        if args.wait:
            print("\n⏳ Waiting for resources to be ready...")

            all_ready = True

            # Wait for models
            for model_id in created_resources["models"]:
                if not wait_for_resource_ready(
                    lisa_client, "model", model_id, lambda mid: check_model_ready(lisa_client, mid)
                ):
                    all_ready = False

            # Wait for repositories
            for repo_id in created_resources["repositories"]:
                if not wait_for_resource_ready(
                    lisa_client, "repository", repo_id, lambda rid: check_repository_ready(lisa_client, rid)
                ):
                    all_ready = False

            if all_ready:
                print("\n🎉 All resources are ready!")
            else:
                print("\n⚠️  Some resources may not be ready yet")

        # Clean up if requested
        if args.cleanup:
            cleanup_resources(lisa_client, created_resources)
            print("\n🧹 Cleanup completed!")
        else:
            print("\n💡 To clean up resources later, run this script with --cleanup flag")
            print("   Or manually delete the resources through the LISA UI")

        print("\n✅ Integration setup test completed successfully!")
        return 0

    except Exception as e:
        print(f"\n❌ Integration setup test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
