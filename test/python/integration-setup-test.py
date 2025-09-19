#!/usr/bin/env python3
"""
Integration test script that deploys resources to LISA.
This script creates:
- A Bedrock model
- A self-hosted model
- A PGVector repository
- An OpenSearch repository
"""

import os
import sys
import time
import argparse
import boto3
from typing import Dict, Any

# Add lisa-sdk to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lisa-sdk'))

from lisapy.api import LisaApi
from lisapy.types import BedrockModelRequest, ModelRequest

DEFAULT_EMBEDDING_MODEL_ID='e5-embed'
RAG_PIPELINE_BUCKET='lisa-rag-pipeline'

def get_management_key(deployment_name: str) -> str:
    """Retrieve management key from AWS Secrets Manager.
    
    Args:
        deployment_name: The LISA deployment name
        
    Returns:
        str: The management API key
    """
    secret_name = f"{deployment_name}-lisa-management-key"
    
    try:
        secrets_client = boto3.client('secretsmanager')
        response = secrets_client.get_secret_value(SecretId=secret_name)
        # Secret is stored as a plain string, not JSON
        api_key = response['SecretString']
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
        dynamodb = boto3.resource('dynamodb')
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


def setup_authentication(deployment_name: str) -> Dict[str, str]:
    """Set up authentication for LISA API calls.
    
    Args:
        deployment_name: The LISA deployment name
        
    Returns:
        Dict[str, str]: Authentication headers
    """
    print(f"🔑 Setting up authentication for deployment: {deployment_name}")
    
    # Get management key from AWS Secrets Manager
    api_key = get_management_key(deployment_name)
    
    # Create API token in DynamoDB (optional - for tracking purposes)
    try:
        create_api_token(deployment_name, api_key)
    except Exception as e:
        print(f"⚠️  Failed to create DynamoDB token (proceeding anyway): {e}")
    
    # Return authentication headers (same as conftest.py)
    headers = {
        "Api-Key": api_key,
        "Authorization": api_key
    }
    
    print("✓ Authentication setup completed")
    print(f"✓ Using API key: {api_key[:8]}...")  # Show first 8 chars for debugging
    return headers


def wait_for_resource_ready(lisa_client: LisaApi, resource_type: str, resource_id: str,
                          check_func, max_wait_minutes: int = 30) -> bool:
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
        status = model.get('status', 'Unknown')
        print(f"    Model status: {status}")
        return status == 'InService'
    except Exception:
        return False


def check_repository_ready(lisa_client: LisaApi, repository_id: str) -> bool:
    """Check if a repository is ready by checking status."""
    try:
        status = lisa_client.get_repository_status()
        repo_status = status.get(repository_id, 'Unknown')
        print(f"    Repository status: {repo_status}")
        # Repository is ready when it's not in Creating or Failed state
        return repo_status not in ['Creating', 'Failed', 'Unknown']
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
        lisa_client.get_repository(repository_id)
        return True
    except Exception:
        return False


def create_bedrock_model(lisa_client: LisaApi, model_id: str, model_name: str) -> Dict[str, Any]:
    """Create a Bedrock model configuration."""
    
    # Check if model already exists
    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Bedrock model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}
    
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
        "modelType": "textgen",
        "modelUrl": "",
        "streaming": True,
        "features": [
            {"name": "summarization", "overview": ""},
            {"name": "imageInput", "overview": ""}
        ],
        "features": [],
        "allowedGroups": None
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

def create_self_hosted_embedded_model(lisa_client: LisaApi, model_id: str, model_name: str, base_image: str = 'ghcr.io/huggingface/text-embeddings-inference:latest') -> Dict[str, Any]:
    """Create a self-hosted embedded model configuration."""
    
    # Check if model already exists
    if model_exists(lisa_client, model_id):
        print(f"\n⏭️  Self-hosted embedded model '{model_id}' already exists, skipping creation")
        return {"modelId": model_id}
        
    print(f"\n🚀 Creating self-hosted embedded model '{model_id}'...")

    self_hosted_embedded_model_request: ModelRequest = {
        "autoScalingConfig": {
            "blockDeviceVolumeSize": 30,
            "minCapacity": 1,
            "maxCapacity": 1,
            "cooldown": 420,
            "defaultInstanceWarmup": 180,
            "metricConfig": {
                "albMetricName": "RequestCountPerTarget",
                "targetValue": 30,
                "duration": 60,
                "estimatedInstanceWarmup": 330
            }
        },
        "containerConfig": {
            "image": {
                "baseImage": base_image,
                "type": "asset"
            },
            "sharedMemorySize": 2048,
            "healthCheckConfig": {
                "command": [
                    "CMD-SHELL",
                    "exit 0"
                ],
                "interval": 10,
                "startPeriod": 30,
                "timeout": 5,
                "retries": 3
            },
            "environment": {
                "MAX_BATCH_TOKENS": "16384",
                "MAX_CONCURRENT_REQUESTS": "512",
                "MAX_CLIENT_BATCH_SIZE": "1024"
            }
        },
        "inferenceContainer": "tei",
        "instanceType": "g5.xlarge",
        "loadBalancerConfig": {
            "healthCheckConfig": {
                "path": "/health",
                "interval": 60,
                "timeout": 30,
                "healthyThresholdCount": 2,
                "unhealthyThresholdCount": 10
            }
        },
        "modelId": model_id,
        "modelName": model_name,
        "modelDescription": f"Testing model for {model_name}",
        "modelType": "embedding",
        "streaming": False,
        "features": [],
        "allowedGroups": None
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


def create_self_hosted_model(lisa_client: LisaApi, model_id: str, model_name: str, base_image: str = 'vllm/vllm-openai:latest') -> Dict[str, Any]:
    """Create a self-hosted model configuration."""
    
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
    gpu_instances = [inst for inst in instances if 'g5' in inst.lower() or 'p3' in inst.lower() or 'p4' in inst.lower()]
    instance_type = gpu_instances[0] if gpu_instances else instances[0]
    print(f"  Using instance type: {instance_type}")
    self_hosted_model_request: ModelRequest = {
        "autoScalingConfig": {
            "blockDeviceVolumeSize": 30,
            "minCapacity": 1,
            "maxCapacity": 1,
            "cooldown": 420,
            "defaultInstanceWarmup": 180,
            "metricConfig": {
                "albMetricName": "RequestCountPerTarget",
                "targetValue": 30,
                "duration": 60,
                "estimatedInstanceWarmup": 330
            }
        },
        "containerConfig": {
            "image": {
                "baseImage": base_image,
                "type": "asset"
            },
            "sharedMemorySize": 2048,
            "healthCheckConfig": {
                "command": [
                    "CMD-SHELL",
                    "exit 0"
                ],
                "interval": 10,
                "startPeriod": 30,
                "timeout": 5,
                "retries": 3
            },
            "environment": {
                "MAX_TOTAL_TOKENS": "2048",
                "MAX_CONCURRENT_REQUESTS": "128",
                "MAX_INPUT_LENGTH": "1024"
            }
        },
        "inferenceContainer": "vllm",
        "instanceType": "g5.xlarge",
        "loadBalancerConfig": {
            "healthCheckConfig": {
                "path": "/health",
                "interval": 60,
                "timeout": 30,
                "healthyThresholdCount": 2,
                "unhealthyThresholdCount": 10
            }
        },
        "modelId": model_id,
        "modelName": model_name,
        "modelDescription": None,
        "modelType": "textgen",
        "streaming": True,
        "features": [
            {
                "name": "summarization",
                "overview": ""
            },
            {
                "name": "imageInput",
                "overview": ""
            }
        ],
        "allowedGroups": None
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


def create_pgvector_repository(lisa_client: LisaApi, embedding_model_id: str = None) -> Dict[str, Any]:
    """Create a PGVector repository."""
    repository_id = "test-pgvector-rag"
    
    # Check if repository already exists
    if repository_exists(lisa_client, repository_id):
        print(f"\n⏭️  PGVector repository '{repository_id}' already exists, skipping creation")
        return {"repositoryId": repository_id}
    
    print(f"\n🚀 Creating PGVector repository '{repository_id}'...")
    
    try:
        rag_config = {
            "repositoryId": repository_id,
            "embeddingModelId": DEFAULT_EMBEDDING_MODEL_ID,
            "type": "pgvector",
            "rdsConfig": {
                "username": "postgres",
                "passwordSecretId": "",
                "dbHost": "",
                "dbName": "postgres",
                "dbPort": 5432
            },
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseName": "",
                "bedrockKnowledgeBaseId": "",
                "bedrockKnowledgeDatasourceName": "",
                "bedrockKnowledgeDatasourceId": "",
                "bedrockKnowledgeDatasourceS3Bucket": ""
            },
            "pipelines": [
                {
                    "chunkSize": 512,
                    "chunkOverlap": 51,
                    "embeddingModel": DEFAULT_EMBEDDING_MODEL_ID,
                    "s3Bucket": RAG_PIPELINE_BUCKET,
                    "s3Prefix": "",
                    "trigger": "event",
                    "autoRemove": True
                }
            ],
            "allowedGroups": []
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


def create_opensearch_repository(lisa_client: LisaApi, embedding_model_id: str = None) -> Dict[str, Any]:
    """Create an OpenSearch repository."""
    repository_id = "test-opensearch-rag"
    
    # Check if repository already exists
    if repository_exists(lisa_client, repository_id):
        print(f"\n⏭️  OpenSearch repository '{repository_id}' already exists, skipping creation")
        return {"repositoryId": repository_id}
    
    print(f"\n🚀 Creating OpenSearch repository '{repository_id}'...")
    
    try:
        rag_config = {
            "repositoryId": repository_id,
            "embeddingModelId": DEFAULT_EMBEDDING_MODEL_ID,
            "type": "opensearch",
            "opensearchConfig": {
                "endpoint": ""
            },
            "rdsConfig": {
                "username": "postgres",
                "passwordSecretId": "",
                "dbHost": "",
                "dbName": "postgres",
                "dbPort": 5432
            },
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseName": "",
                "bedrockKnowledgeBaseId": "",
                "bedrockKnowledgeDatasourceName": "",
                "bedrockKnowledgeDatasourceId": "",
                "bedrockKnowledgeDatasourceS3Bucket": ""
            },
            "pipelines": [
                {
                    "chunkSize": 512,
                    "chunkOverlap": 51,
                    "embeddingModel": DEFAULT_EMBEDDING_MODEL_ID,
                    "s3Bucket": RAG_PIPELINE_BUCKET,
                    "s3Prefix": "",
                    "trigger": "event",
                    "autoRemove": True
                }
            ],
            "allowedGroups": []
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


def cleanup_resources(lisa_client: LisaApi, created_resources: Dict[str, list]):
    """Clean up created resources."""
    print("\n🧹 Cleaning up created resources...")
    
    # Clean up models
    for model_id in created_resources.get('models', []):
        try:
            lisa_client.delete_model(model_id)
            print(f"✓ Deleted model: {model_id}")
        except Exception as e:
            print(f"✗ Failed to delete model {model_id}: {e}")
    
    # Clean up repositories  
    for repo_id in created_resources.get('repositories', []):
        try:
            lisa_client.delete_repository(repo_id)
            print(f"✓ Deleted repository: {repo_id}")
        except Exception as e:
            print(f"✗ Failed to delete repository {repo_id}: {e}")


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description='LISA Integration Setup Test')
    parser.add_argument('--url', required=True, help='LISA ALB URL')
    parser.add_argument('--api', required=True, help='LISA API URL')
    parser.add_argument('--deployment-name', required=True, help='LISA deployment name for authentication')
    parser.add_argument('--verify', default='false', help='Verify SSL certificates')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--cleanup', action='store_true', help='Clean up resources after test')
    parser.add_argument('--wait', action='store_true', help='Wait for resources to be ready')
    
    args = parser.parse_args()
    
    # Convert verify to boolean
    verify_ssl = args.verify.lower() not in ['false', '0', 'no', 'off']
    
    print("🚀 LISA Integration Setup Test Starting...")
    print(f"ALB URL: {args.url}")
    print(f"API URL: {args.api}") 
    print(f"Deployment Name: {args.deployment_name}")
    print(f"Verify SSL: {verify_ssl}")
    print(f"AWS Profile: {args.profile}")
    
    try:
        # Setup authentication
        auth_headers = setup_authentication(args.deployment_name)
        
        # Initialize LISA client with authentication
        lisa_client = LisaApi(
            url=args.api,
            verify=verify_ssl,
            headers=auth_headers
        )
        
        created_resources = {'models': [], 'repositories': []}
        
        # Get an embedding model for repositories
        embedding_models = lisa_client.list_embedding_models()
        embedding_model_id = None
        if embedding_models:
            embedding_model_id = embedding_models[0].get('modelId')
            print(f"Using embedding model: {embedding_model_id}")
        else:
            print("⚠️  No embedding models found, repositories will be created without default embedding model")
        
        models = []
        # # 1. Create Bedrock model
        models.append(create_bedrock_model(lisa_client, "nova-lite", "bedrock/us.amazon.nova-lite-v1:0"))
        models.append(create_bedrock_model(lisa_client, "sonnet-4", "bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0"))
        
        # # 2. Create self-hosted model
        models.append(create_self_hosted_model(lisa_client, "mistral-7b-instruct-03", "mistralai/Mistral-7B-Instruct-v0.3"))
        models.append(create_self_hosted_model(lisa_client, "llama-32-3b", "meta-llama/Llama-3.2-3B"))
        
        # # 3. Create self-hosted embedded model
        models.append(create_self_hosted_embedded_model(lisa_client, DEFAULT_EMBEDDING_MODEL_ID, "intfloat/e5-large-v2"))
        models.append(create_self_hosted_embedded_model(lisa_client, "qwen3-embed-06b", "Qwen/Qwen3-Embedding-0.6B"))
        models.append(create_self_hosted_embedded_model(lisa_client, "baai-embed-15", "BAAI/bge-large-en-v1.5"))

        for model in models:
            created_resources['models'].append(model["modelId"])

        # # 4. Create PGVector repository
        pgvector_repo = create_pgvector_repository(lisa_client, embedding_model_id)
        created_resources['repositories'].append(pgvector_repo['repositoryId'])
        
        # # # 5. Create OpenSearch repository
        opensearch_repo = create_opensearch_repository(lisa_client, embedding_model_id)
        created_resources['repositories'].append(opensearch_repo['repositoryId'])
        
        print("\n✅ All resources created successfully!")
        print("Created resources:")
        print(f"  Models: {created_resources['models']}")
        print(f"  Repositories: {created_resources['repositories']}")
        
        # Wait for resources to be ready if requested
        if args.wait:
            print("\n⏳ Waiting for resources to be ready...")
            
            all_ready = True
            
            # Wait for models
            for model_id in created_resources['models']:
                if not wait_for_resource_ready(
                    lisa_client, 'model', model_id, 
                    lambda mid: check_model_ready(lisa_client, mid)
                ):
                    all_ready = False
            
            # Wait for repositories
            for repo_id in created_resources['repositories']:
                if not wait_for_resource_ready(
                    lisa_client, 'repository', repo_id,
                    lambda rid: check_repository_ready(lisa_client, rid)
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
