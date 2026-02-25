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
- Self-hosted and Bedrock models (textgen and embedding)
- PGVector, OpenSearch, and Bedrock Knowledge Base repositories

To control what gets deployed, edit the deploy_* lists in integration_definitions.py.
To add a new resource, add an entry to the appropriate *_DEFINITIONS dict there.
"""

import argparse
import json
import os
import sys
import time
from typing import Any

import boto3

# Add lisa-sdk and the test directory itself to path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "../../lisa-sdk"))
sys.path.insert(0, _HERE)

from integration_definitions import (
    BEDROCK_KB_S3_BUCKET,
    BEDROCK_MODEL_DEFINITIONS,
    DEFAULT_AUTOSCALING_SCHEDULE,
    DEFAULT_EMBEDDING_MODEL_ID,
    deploy_bedrock_models,
    deploy_embedded_models,
    deploy_models,
    deploy_vector_stores,
    EMBEDDED_MODEL_DEFINITIONS,
    MODEL_DEFINITIONS,
    VECTOR_STORE_DEFINITIONS,
)
from lisapy.api import LisaApi
from lisapy.types import BedrockModelRequest, ModelRequest

# ---------------------------------------------------------------------------
# Helper / utility functions
# ---------------------------------------------------------------------------


def get_management_key(deployment_name: str, deployment_stage: str, region: str | None = None) -> str:
    """Retrieve management key from AWS Secrets Manager."""
    secret_name = f"{deployment_name}-management-key"
    print(f"  Looking for secret: {secret_name}")
    if region:
        print(f"  Using region: {region}")

    try:
        secrets_client = (
            boto3.client("secretsmanager", region_name=region) if region else boto3.client("secretsmanager")
        )
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    except Exception as e:
        print(f"✗ Failed to retrieve management key from {secret_name}: {e}")
        raise


def create_api_token(deployment_name: str, api_key: str) -> str:
    """Create an API token in DynamoDB with expiration."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(f"{deployment_name}-LISAApiTokenTable")
        current_time = int(time.time())
        table.put_item(Item={"token": api_key, "tokenExpiration": current_time + 3600})
        print(f"✓ Created API token with expiration: {current_time + 3600}")
        return api_key
    except Exception as e:
        print(f"✗ Failed to create API token: {e}")
        raise


def setup_authentication(deployment_name: str, deployment_stage: str) -> dict[str, str]:
    """Set up authentication for LISA API calls."""
    print(f"🔑 Setting up authentication for deployment: {deployment_name}")
    api_key = get_management_key(deployment_name, deployment_stage)
    headers = {"Api-Key": api_key, "Authorization": api_key}
    print("✓ Authentication setup completed")
    print(f"✓ Using API key: {api_key[:8]}...")
    return headers


def wait_for_resource_ready(
    lisa_client: LisaApi, resource_type: str, resource_id: str, check_func, max_wait_minutes: int = 30
) -> bool:
    """Wait for a resource to be ready/deployed."""
    print(f"Waiting for {resource_type} '{resource_id}' to be ready...")
    max_iterations = max_wait_minutes * 4
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
    """Check if a repository is ready."""
    try:
        status = lisa_client.get_repository_status()
        repo_status = status.get(repository_id, "Unknown")
        print(f"    Repository status: {repo_status}")
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


# ---------------------------------------------------------------------------
# Resource creation functions
# ---------------------------------------------------------------------------


def create_bedrock_model(
    lisa_client: LisaApi,
    model_id: str,
    definition: dict,
    skip_create: bool = False,
) -> dict[str, Any]:
    """Create a Bedrock model from a definition dict."""
    if skip_create:
        print(f"\n⏭️  Skipping creation of Bedrock model '{model_id}' (skip_create=True)")
        return {"modelId": model_id}

    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Bedrock model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}

    modelName = definition.get("model_name")
    model_type = definition.get("model_type", "textgen")
    features = definition.get(
        "features",
        [
            {"name": "summarization", "overview": ""},
            {"name": "imageInput", "overview": ""},
            {"name": "reasoning", "overview": ""},
            {"name": "toolCalls", "overview": ""},
        ],
    )
    description = definition.get("description", f"Bedrock model {modelName}")

    print(f"\n🚀 Creating Bedrock model '{model_id}'...")

    bedrock_model_request: BedrockModelRequest = {
        "autoScalingConfig": None,
        "containerConfig": None,
        "inferenceContainer": None,
        "instanceType": None,
        "loadBalancerConfig": None,
        "modelId": model_id,
        "modelName": modelName,
        "modelDescription": description,
        "modelType": model_type,
        "modelUrl": "",
        "streaming": model_type != "embedding",
        "features": features,
        "allowedGroups": None,
    }

    try:
        result = lisa_client.create_bedrock_model(bedrock_model_request)
        print(f"✓ Bedrock model created: {result}")
        if result is None or not isinstance(result, dict):
            result = {"modelId": model_id}
        elif "modelId" not in result:
            result["modelId"] = model_id
        return result
    except Exception as e:
        print(f"✗ Failed to create Bedrock model: {e}")
        raise


def create_self_hosted_embedded_model(
    lisa_client: LisaApi,
    model_id: str,
    definition: dict,
    base_image: str = "ghcr.io/huggingface/text-embeddings-inference:latest",
    skip_create: bool = False,
) -> dict[str, Any]:
    """Create a self-hosted embedding model from a definition dict."""
    if skip_create:
        print(f"\n⏭️  Skipping creation of self-hosted embedded model '{model_id}' (skip_create=True)")
        return {"modelId": model_id}

    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Self-hosted embedded model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}

    instance_type = definition.get("instance_type", "g6.xlarge")
    model_name = definition["model_name"]
    description = definition.get("description", f"Self-hosted embedding model for {model_name}")
    default_environment: dict[str, str] = {
        "MAX_BATCH_TOKENS": "16384",
        "MAX_CONCURRENT_REQUESTS": "512",
        "MAX_CLIENT_BATCH_SIZE": "256",
        "POOLING": "mean",
        "AUTO_TRUNCATE": "true",
        "DTYPE": "float16",
    }
    resolved_environment = {**default_environment, **definition.get("environment", {})}

    print(f"\n🚀 Creating self-hosted embedded model '{model_id}' on {instance_type}...")

    request: ModelRequest = {
        "autoScalingConfig": {
            "blockDeviceVolumeSize": 50,
            "minCapacity": 1,
            "maxCapacity": 1,
            "cooldown": 420,
            "defaultInstanceWarmup": 300,
            "metricConfig": {
                "albMetricName": "RequestCountPerTarget",
                "targetValue": 30,
                "duration": 60,
                "estimatedInstanceWarmup": 300,
            },
            "scheduling": DEFAULT_AUTOSCALING_SCHEDULE,
        },
        "containerConfig": {
            "image": {
                "baseImage": base_image,
                "type": "ecr" if base_image.split(".")[0].isdigit() else "asset",
            },
            "healthCheckConfig": {
                "command": ["CMD-SHELL", "exit 0"],
                "interval": 10,
                "startPeriod": 300,
                "timeout": 5,
                "retries": 3,
            },
            "environment": resolved_environment,
            "sharedMemorySize": definition.get("sharedMemorySize", 2048),
            **(
                {"memoryReservation": definition["memoryReservation"]}
                if "memoryReservation" in definition
                else {"memoryReservation": 12836}
            ),
        },
        "inferenceContainer": "tei",
        "instanceType": instance_type,
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
        "modelDescription": description,
        "modelType": "embedding",
        "streaming": False,
        "features": [],
        "allowedGroups": None,
    }

    try:
        result = lisa_client.create_self_hosted_embedded_model(request)
        print(f"✓ Self-hosted embedded model created: {result}")
        if result is None or not isinstance(result, dict):
            result = {"modelId": model_id}
        elif "modelId" not in result:
            result["modelId"] = model_id
        return result
    except Exception as e:
        print(f"✗ Failed to create self-hosted embedded model: {e}")
        raise


def create_self_hosted_model(
    lisa_client: LisaApi,
    model_id: str,
    definition: dict,
    base_image: str,
    skip_create: bool = False,
) -> dict[str, Any]:
    """Create a self-hosted textgen model from a definition dict."""
    if skip_create:
        print(f"\n⏭️  Skipping creation of self-hosted model '{model_id}' (skip_create=True)")
        return {"modelId": model_id}

    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Self-hosted model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}

    instances = lisa_client.list_instances()
    if not instances:
        raise Exception("No EC2 instances available for self-hosted model")

    instance_type = definition.get("instance_type", "g6.xlarge")
    model_name = definition["model_name"]
    environment = definition.get(
        "environment",
        {
            "VLLM_MAX_MODEL_LEN": "16384",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "128",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_DTYPE": "auto",
        },
    )
    block_device = definition.get("blockDeviceVolumeSize", 50)
    shared_mem = definition.get("sharedMemorySize", 2048)
    mem_reservation = definition.get("memoryReservation", None)
    description = definition.get("description", f"Self-hosted model for {model_name}")
    features = definition.get(
        "features",
        [
            {"name": "summarization", "overview": ""},
            {"name": "reasoning", "overview": ""},
            {"name": "toolCalls", "overview": ""},
        ],
    )
    print(f"\n🚀 Creating self-hosted model '{model_id}' on {instance_type}...")

    request: ModelRequest = {
        "autoScalingConfig": {
            "blockDeviceVolumeSize": block_device,
            "minCapacity": 1,
            "maxCapacity": 1,
            "cooldown": 420,
            "defaultInstanceWarmup": 300,
            "metricConfig": {
                "albMetricName": "RequestCountPerTarget",
                "targetValue": 30,
                "duration": 60,
                "estimatedInstanceWarmup": 300,
            },
            "scheduling": DEFAULT_AUTOSCALING_SCHEDULE,
        },
        "containerConfig": {
            "image": {
                "baseImage": base_image,
                "type": "ecr" if base_image.split(".")[0].isdigit() else "asset",
            },
            "sharedMemorySize": shared_mem,
            "healthCheckConfig": {
                "command": ["CMD-SHELL", "exit 0"],
                "interval": 10,
                "startPeriod": 300,
                "timeout": 5,
                "retries": 3,
            },
            "environment": environment,
            **({"memoryReservation": mem_reservation} if mem_reservation is not None else {}),
        },
        "inferenceContainer": "vllm",
        "instanceType": instance_type,
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
        "modelDescription": description,
        "modelType": "textgen",
        "streaming": True,
        "features": features,
        "allowedGroups": None,
    }

    try:
        result = lisa_client.create_self_hosted_model(request)
        print(f"✓ Self-hosted model created: {result}")
        if result is None or not isinstance(result, dict):
            result = {"modelId": model_id}
        elif "modelId" not in result:
            result["modelId"] = model_id
        return result
    except Exception as e:
        print(f"✗ Failed to create self-hosted model: {e}")
        raise


def create_vector_store(
    lisa_client: LisaApi,
    repository_id: str,
    definition: dict,
    embedding_model_id: str | None,
    skip_create: bool = False,
    # Extra runtime args needed for bedrock_knowledge_base type
    knowledge_base_id: str | None = None,
    data_source_id: str | None = None,
    data_source_name: str | None = None,
    s3_bucket: str | None = None,
) -> dict[str, Any]:
    """Create a vector store repository from a definition dict."""
    store_type = definition["type"]

    if skip_create:
        print(f"\n⏭️  Skipping creation of {store_type} repository '{repository_id}' (skip_create=True)")
        return {"repositoryId": repository_id}

    if repository_exists(lisa_client, repository_id):
        print(f"\n⏭️  Repository '{repository_id}' already exists, skipping creation")
        return {"repositoryId": repository_id}

    print(f"\n🚀 Creating {store_type} repository '{repository_id}'...")

    config = {
        **definition["config"],
        "repositoryId": repository_id,
        "embeddingModelId": embedding_model_id or DEFAULT_EMBEDDING_MODEL_ID,
        "type": store_type,
        **({"description": definition["description"]} if "description" in definition else {}),
    }

    try:
        if store_type == "pgvector":
            result = lisa_client.create_pgvector_repository(config)
        elif store_type == "bedrock_knowledge_base":
            config["bedrockKnowledgeBaseConfig"] = {
                "knowledgeBaseId": knowledge_base_id,
                "dataSources": [
                    {
                        "id": data_source_id,
                        "name": data_source_name,
                        "s3Uri": f"s3://{s3_bucket}/",
                    }
                ],
            }
            result = lisa_client.create_bedrock_kb_repository(config)
        else:
            result = lisa_client.create_repository(config)

        print(f"✓ Repository created: {result}")
        if result is None or not isinstance(result, dict):
            result = {"repositoryId": repository_id}
        elif "repositoryId" not in result:
            result["repositoryId"] = repository_id
        return result
    except Exception as e:
        print(f"✗ Failed to create repository '{repository_id}': {e}")
        raise


def create_bedrock_knowledge_base(
    deployment_name: str,
    region: str,
    kb_name: str = "bedrock-kb-e2e-test",
    s3_bucket_name: str = BEDROCK_KB_S3_BUCKET,
    embedding_model_arn: str | None = None,
    skip_create: bool = False,
) -> dict[str, Any]:
    """Create a Bedrock Knowledge Base with S3 data source."""
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

        account_id = sts_client.get_caller_identity()["Account"]
        bucket_name = f"{deployment_name}-{s3_bucket_name}"

        # 1. Ensure S3 bucket exists
        print(f"  Checking S3 bucket: {bucket_name}")
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✓ S3 bucket already exists: {bucket_name}")
        except s3_client.exceptions.NoSuchBucket:
            if region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})
            print(f"✓ S3 bucket created: {bucket_name}")
        except Exception as e:
            print(f"⚠️  S3 bucket check issue: {e}")

        # 2. Create IAM role
        role_name = f"{deployment_name}-BedrockKBRole"
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Principal": {"Service": "bedrock.amazonaws.com"}, "Action": "sts:AssumeRole"}
            ],
        }
        try:
            role_arn = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Role for Bedrock Knowledge Base - {deployment_name}",
            )["Role"]["Arn"]
            print(f"✓ IAM role created: {role_arn}")
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-Policy",
                PolicyDocument=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["s3:GetObject", "s3:ListBucket"],
                                "Resource": [f"arn:aws:s3:::{bucket_name}", f"arn:aws:s3:::{bucket_name}/*"],
                            },
                            {"Effect": "Allow", "Action": ["bedrock:InvokeModel"], "Resource": "*"},
                            {"Effect": "Allow", "Action": ["aoss:APIAccessAll"], "Resource": "*"},
                        ],
                    }
                ),
            )
            time.sleep(10)
        except iam_client.exceptions.EntityAlreadyExistsException:
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
            print(f"✓ IAM role already exists: {role_arn}")

        # 3. Create OpenSearch Serverless collection
        collection_name = f"{deployment_name}-kb-collection"
        collection_id = None
        collection_arn = None

        try:
            enc_policy_name = f"{deployment_name}-kb-encryption"
            net_policy_name = f"{deployment_name}-kb-network"
            data_policy_name = f"{deployment_name}-kb-data-access"

            for policy_call in [
                lambda: aoss_client.create_security_policy(
                    name=enc_policy_name,
                    type="encryption",
                    policy=json.dumps(
                        {
                            "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{collection_name}"]}],
                            "AWSOwnedKey": True,
                        }
                    ),
                    description=f"Encryption policy for {collection_name}",
                ),
                lambda: aoss_client.create_security_policy(
                    name=net_policy_name,
                    type="network",
                    policy=json.dumps(
                        [
                            {
                                "Rules": [
                                    {"ResourceType": "collection", "Resource": [f"collection/{collection_name}"]}
                                ],
                                "AllowFromPublic": True,
                            }
                        ]
                    ),
                    description=f"Network policy for {collection_name}",
                ),
                lambda: aoss_client.create_access_policy(
                    name=data_policy_name,
                    type="data",
                    policy=json.dumps(
                        [
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
                    ),
                    description=f"Data access policy for {collection_name}",
                ),
            ]:
                try:
                    policy_call()
                except aoss_client.exceptions.ConflictException:
                    pass

            resp = aoss_client.create_collection(
                name=collection_name, type="VECTORSEARCH", description=f"Collection for {kb_name}"
            )
            collection_id = resp["createCollectionDetail"]["id"]
            collection_arn = resp["createCollectionDetail"]["arn"]
            print(f"✓ OpenSearch Serverless collection created: {collection_id}")

            for _ in range(60):
                status = aoss_client.batch_get_collection(ids=[collection_id])
                if status["collectionDetails"][0]["status"] == "ACTIVE":
                    print("✓ Collection is active")
                    break
                time.sleep(5)

        except Exception as e:
            print(f"⚠️  OpenSearch Serverless collection issue: {e}")
            collections = aoss_client.list_collections(collectionFilters={"name": collection_name})
            if collections["collectionSummaries"]:
                collection_id = collections["collectionSummaries"][0]["id"]
                collection_arn = collections["collectionSummaries"][0]["arn"]
                print(f"✓ Using existing collection: {collection_id}")
            else:
                raise

        # 4. Create vector index
        index_name = f"{kb_name}-index"
        try:
            from opensearchpy import OpenSearch, RequestsHttpConnection
            from requests_aws4auth import AWS4Auth

            collection_endpoint = aoss_client.batch_get_collection(ids=[collection_id])["collectionDetails"][0][
                "collectionEndpoint"
            ]
            if collection_endpoint.startswith("https://"):
                collection_endpoint = collection_endpoint[8:]

            credentials = boto3.Session().get_credentials()
            awsauth = AWS4Auth(
                credentials.access_key, credentials.secret_key, region, "aoss", session_token=credentials.token
            )
            os_client = OpenSearch(
                hosts=[{"host": collection_endpoint, "port": 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=30,
            )
            if not os_client.indices.exists(index=index_name):
                os_client.indices.create(
                    index=index_name,
                    body={
                        "settings": {"index.knn": True},
                        "mappings": {
                            "properties": {
                                "embedding": {
                                    "type": "knn_vector",
                                    "dimension": 1024,
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
                    },
                )
                print(f"✓ Created vector index: {index_name}")
            else:
                print(f"✓ Vector index already exists: {index_name}")
        except ImportError:
            print("⚠️  opensearch-py not installed, skipping index creation")
        except Exception as e:
            print(f"⚠️  Could not create vector index: {e}")

        # 5. Check for existing KB
        if not embedding_model_arn:
            embedding_model_arn = f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"

        existing_kb_id = None
        existing_ds_id = None
        try:
            for kb in bedrock_agent_client.list_knowledge_bases().get("knowledgeBaseSummaries", []):
                if kb.get("name") == kb_name:
                    existing_kb_id = kb["knowledgeBaseId"]
                    ds_list = bedrock_agent_client.list_data_sources(knowledgeBaseId=existing_kb_id)
                    if ds_list.get("dataSourceSummaries"):
                        existing_ds_id = ds_list["dataSourceSummaries"][0]["dataSourceId"]
                    break
        except Exception as e:
            print(f"  Could not check existing knowledge bases: {e}")

        if existing_kb_id:
            print("✓ Using existing Bedrock Knowledge Base")
            return {
                "knowledgeBaseId": existing_kb_id,
                "dataSourceId": existing_ds_id,
                "s3Bucket": bucket_name,
                "collectionId": collection_id,
                "roleArn": role_arn,
            }

        # 6. Create KB
        kb_response = bedrock_agent_client.create_knowledge_base(
            name=kb_name,
            description=f"Test Knowledge Base for LISA integration testing - {deployment_name}",
            roleArn=role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {"embeddingModelArn": embedding_model_arn},
            },
            storageConfiguration={
                "type": "OPENSEARCH_SERVERLESS",
                "opensearchServerlessConfiguration": {
                    "collectionArn": collection_arn,
                    "vectorIndexName": index_name,
                    "fieldMapping": {"vectorField": "embedding", "textField": "text", "metadataField": "metadata"},
                },
            },
        )
        knowledge_base_id = kb_response["knowledgeBase"]["knowledgeBaseId"]
        print(f"✓ Knowledge Base created: {knowledge_base_id}")

        # 7. Create data source
        ds_response = bedrock_agent_client.create_data_source(
            knowledgeBaseId=knowledge_base_id,
            name=f"{kb_name}-s3-source",
            description=f"S3 data source for {kb_name}",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {"bucketArn": f"arn:aws:s3:::{bucket_name}", "inclusionPrefixes": ["documents/"]},
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


# ---------------------------------------------------------------------------
# Cleanup functions
# ---------------------------------------------------------------------------


def cleanup_all_models(lisa_client: LisaApi) -> None:
    """Clean up all models."""
    print("\n🧹 Cleaning up all models...")
    try:
        models = lisa_client.list_models()
        if not models:
            print("  No models found to delete")
            return
        print(f"  Found {len(models)} models to delete")
        for model in models:
            model_id = model.get("modelId")
            if model_id:
                try:
                    lisa_client.delete_model(model_id)
                    print(f"✓ Deleted model: {model_id}")
                except Exception as e:
                    print(f"✗ Failed to delete model {model_id}: {e}")
    except Exception as e:
        print(f"✗ Failed to list models for cleanup: {e}")


def cleanup_all_repositories(lisa_client: LisaApi) -> None:
    """Clean up all repositories."""
    print("\n🧹 Cleaning up all repositories...")
    try:
        repositories = lisa_client.list_repositories()
        if not repositories:
            print("  No repositories found to delete")
            return
        print(f"  Found {len(repositories)} repositories to delete")
        for repo in repositories:
            repo_id = repo.get("repositoryId")
            if repo_id:
                try:
                    lisa_client.delete_repository(repo_id)
                    print(f"✓ Deleted repository: {repo_id}")
                except Exception as e:
                    print(f"✗ Failed to delete repository {repo_id}: {e}")
    except Exception as e:
        print(f"✗ Failed to list repositories for cleanup: {e}")


def cleanup_resources(lisa_client: LisaApi, created_resources: dict[str, list]) -> None:
    """Clean up all created resources including Bedrock Knowledge Bases."""
    print("\n🧹 Cleaning up resources...")
    cleanup_all_models(lisa_client)
    cleanup_all_repositories(lisa_client)

    for kb_info in created_resources.get("knowledge_bases", []):
        try:
            bedrock_agent_client = boto3.client("bedrock-agent")
            s3_client = boto3.client("s3")
            kb_id = kb_info.get("knowledgeBaseId")
            s3_bucket = kb_info.get("s3Bucket")

            if "dataSourceId" in kb_info:
                try:
                    bedrock_agent_client.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=kb_info["dataSourceId"])
                    print(f"✓ Deleted data source: {kb_info['dataSourceId']}")
                except Exception as e:
                    print(f"✗ Failed to delete data source: {e}")

            try:
                bedrock_agent_client.delete_knowledge_base(knowledgeBaseId=kb_id)
                print(f"✓ Deleted knowledge base: {kb_id}")
            except Exception as e:
                print(f"✗ Failed to delete knowledge base {kb_id}: {e}")

            if s3_bucket:
                try:
                    paginator = s3_client.get_paginator("list_objects_v2")
                    for page in paginator.paginate(Bucket=s3_bucket):
                        if "Contents" in page:
                            s3_client.delete_objects(
                                Bucket=s3_bucket, Delete={"Objects": [{"Key": o["Key"]} for o in page["Contents"]]}
                            )
                    s3_client.delete_bucket(Bucket=s3_bucket)
                    print(f"✓ Deleted S3 bucket: {s3_bucket}")
                except Exception as e:
                    print(f"✗ Failed to delete S3 bucket {s3_bucket}: {e}")
        except Exception as e:
            print(f"✗ Failed to delete knowledge base {kb_info}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="LISA Integration Setup Test")
    parser.add_argument("--url", required=True, help="LISA ALB URL")
    parser.add_argument("--api", required=True, help="LISA API URL")
    parser.add_argument("--deployment-name", required=True, help="LISA deployment name")
    parser.add_argument("--deployment-stage", required=True, help="LISA deployment stage")
    parser.add_argument("--deployment-prefix", required=True, help="LISA deployment prefix")
    parser.add_argument("--region", help="AWS region (overrides AWS_DEFAULT_REGION / AWS_REGION env vars)")
    parser.add_argument("--verify", default="true", help="Verify SSL certificates (default: true)")
    parser.add_argument("--profile", help="AWS profile to use")
    parser.add_argument("--cleanup", action="store_true", help="Delete all models and repositories")
    parser.add_argument("--skip-create", action="store_true", help="Skip creation, only collect IDs")
    parser.add_argument("--wait", action="store_true", help="Wait for resources to be ready")

    args = parser.parse_args()
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
        auth_headers = setup_authentication(args.deployment_name, args.deployment_stage)

        sts_client = boto3.client("sts")
        account_id = sts_client.get_caller_identity()["Account"]
        region = args.region or os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
        print(f"Account ID: {account_id}")
        print(f"Region: {region}")

        lisa_client = LisaApi(url=args.api, verify=verify_ssl, headers=auth_headers)
        created_resources: dict[str, list] = {"models": [], "repositories": [], "knowledge_bases": []}

        if args.cleanup:
            print("\n🧹 Cleanup mode: Skipping resource creation and performing cleanup...")
            created_resources["knowledge_bases"] = [
                {
                    "knowledgeBaseId": "bedrock-kb-e2e-test-id",
                    "dataSourceId": "bedrock-kb-e2e-test-ds-id",
                    "s3Bucket": f"{args.deployment_name}-{BEDROCK_KB_S3_BUCKET}",
                }
            ]
            cleanup_resources(lisa_client, created_resources)
            print("\n✅ Integration setup test completed successfully!")
            return 0

        # Resolve embedding model for repositories
        embedding_models = lisa_client.list_embedding_models()
        embedding_model_id = embedding_models[0].get("modelId") if embedding_models else None
        if embedding_model_id:
            print(f"Using embedding model: {embedding_model_id}")
        else:
            print("⚠️  No embedding models found, repositories will use default embedding model")

        # vllm_base_image = f"{account_id}.dkr.ecr.{region}.amazonaws.com/lisa-vllm:latest"
        vllm_base_image = "public.ecr.aws/deep-learning-containers/vllm:0.15-gpu-py312-ec2"

        # Deploy self-hosted textgen models
        for model_id in deploy_models:
            if model_id not in MODEL_DEFINITIONS:
                print(f"⚠️  Unknown model '{model_id}' in deploy_models, skipping")
                continue
            definition = MODEL_DEFINITIONS[model_id]
            result = create_self_hosted_model(
                lisa_client,
                model_id,
                definition,
                base_image=definition.get("base_image", vllm_base_image),
                skip_create=args.skip_create,
            )
            created_resources["models"].append(result["modelId"])

        # Deploy self-hosted embedding models
        for model_id in deploy_embedded_models:
            if model_id not in EMBEDDED_MODEL_DEFINITIONS:
                print(f"⚠️  Unknown embedded model '{model_id}' in deploy_embedded_models, skipping")
                continue
            result = create_self_hosted_embedded_model(
                lisa_client,
                model_id,
                EMBEDDED_MODEL_DEFINITIONS[model_id],
                skip_create=args.skip_create,
            )
            created_resources["models"].append(result["modelId"])

        # Deploy Bedrock models
        for model_id in deploy_bedrock_models:
            if model_id not in BEDROCK_MODEL_DEFINITIONS:
                print(f"⚠️  Unknown Bedrock model '{model_id}' in deploy_bedrock_models, skipping")
                continue
            result = create_bedrock_model(
                lisa_client,
                model_id,
                BEDROCK_MODEL_DEFINITIONS[model_id],
                skip_create=args.skip_create,
            )
            created_resources["models"].append(result["modelId"])

        # Deploy vector stores
        for store_id in deploy_vector_stores:
            if store_id not in VECTOR_STORE_DEFINITIONS:
                print(f"⚠️  Unknown vector store '{store_id}' in deploy_vector_stores, skipping")
                continue

            store_def = VECTOR_STORE_DEFINITIONS[store_id]

            if store_def["type"] == "bedrock_knowledge_base" and store_def.get("create_bedrock_kb"):
                kb_opts = store_def.get("bedrock_kb_options", {})
                kb_result = create_bedrock_knowledge_base(
                    deployment_name=args.deployment_name,
                    region=region,
                    kb_name=kb_opts.get("kb_name", "bedrock-kb-e2e-test"),
                    s3_bucket_name=kb_opts.get("s3_bucket_name", BEDROCK_KB_S3_BUCKET),
                    skip_create=args.skip_create,
                )
                created_resources["knowledge_bases"].append(kb_result)

                if kb_result.get("knowledgeBaseId") and kb_result.get("dataSourceId"):
                    result = create_vector_store(
                        lisa_client,
                        store_id,
                        store_def,
                        embedding_model_id=embedding_model_id,
                        skip_create=args.skip_create,
                        knowledge_base_id=kb_result["knowledgeBaseId"],
                        data_source_id=kb_result["dataSourceId"],
                        data_source_name=f"{kb_opts.get('kb_name', 'bedrock-kb-e2e-test')}-s3-source",
                        s3_bucket=kb_result["s3Bucket"],
                    )
                    created_resources["repositories"].append(result["repositoryId"])
            else:
                result = create_vector_store(
                    lisa_client,
                    store_id,
                    store_def,
                    embedding_model_id=embedding_model_id,
                    skip_create=args.skip_create,
                )
                created_resources["repositories"].append(result["repositoryId"])

        action = "collected" if args.skip_create else "created"
        print(f"\n✅ All resources {action} successfully!")
        print(f"  Models: {created_resources['models']}")
        print(f"  Repositories: {created_resources['repositories']}")
        print(f"  Knowledge Bases: {[kb.get('knowledgeBaseId') for kb in created_resources['knowledge_bases']]}")

        if args.wait:
            print("\n⏳ Waiting for resources to be ready...")
            all_ready = True
            for model_id in created_resources["models"]:
                if not wait_for_resource_ready(
                    lisa_client, "model", model_id, lambda mid: check_model_ready(lisa_client, mid)
                ):
                    all_ready = False
            for repo_id in created_resources["repositories"]:
                if not wait_for_resource_ready(
                    lisa_client, "repository", repo_id, lambda rid: check_repository_ready(lisa_client, rid)
                ):
                    all_ready = False
            print("\n🎉 All resources are ready!" if all_ready else "\n⚠️  Some resources may not be ready yet")

        print("\n💡 To clean up resources later, run this script with --cleanup flag")
        print("\n✅ Integration setup test completed successfully!")
        return 0

    except Exception as e:
        print(f"\n❌ Integration setup test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
