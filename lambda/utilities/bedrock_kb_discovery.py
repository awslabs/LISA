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

"""Discovery service for Bedrock Knowledge Base data sources.

This module provides functionality to discover and list Knowledge Bases and their
data sources from AWS Bedrock Agent APIs. It supports caching and pagination for
efficient resource discovery.
"""

import logging
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from models.domain_objects import ChunkingStrategyType, NoneChunkingStrategy, PipelineTrigger
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)


def list_knowledge_bases(
    bedrock_agent_client: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    List all Knowledge Bases accessible in the AWS account.

    Args:
        bedrock_agent_client: Optional boto3 bedrock-agent client

    Returns:
        List of Knowledge Base metadata dictionaries

    Raises:
        ValidationError: If API call fails
    """
    if not bedrock_agent_client:
        bedrock_agent_client = boto3.client("bedrock-agent")

    try:
        knowledge_bases = []
        next_token = None

        # Handle pagination
        while True:
            list_params = {"maxResults": 100}  # Maximum allowed
            if next_token:
                list_params["nextToken"] = next_token

            response = bedrock_agent_client.list_knowledge_bases(**list_params)

            for kb_summary in response.get("knowledgeBaseSummaries", []):
                knowledge_bases.append(
                    {
                        "knowledgeBaseId": kb_summary.get("knowledgeBaseId"),
                        "name": kb_summary.get("name"),
                        "description": kb_summary.get("description", ""),
                        "status": kb_summary.get("status"),
                        "createdAt": kb_summary.get("createdAt"),
                        "updatedAt": kb_summary.get("updatedAt"),
                    }
                )

            # Check for more pages
            next_token = response.get("nextToken")
            if not next_token:
                break

        logger.info(f"Discovered {len(knowledge_bases)} Knowledge Bases")
        return knowledge_bases

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "AccessDeniedException":
            raise ValidationError(
                "Access denied to list Knowledge Bases. " "Please check IAM permissions for bedrock:ListKnowledgeBases."
            )
        elif error_code == "ThrottlingException":
            raise ValidationError("Rate limit exceeded while listing Knowledge Bases. " "Please try again later.")
        else:
            raise ValidationError(f"Failed to list Knowledge Bases: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error listing Knowledge Bases: {str(e)}", exc_info=True)
        raise ValidationError(f"Unexpected error listing Knowledge Bases: {str(e)}")


def discover_kb_data_sources(
    kb_id: str,
    bedrock_agent_client: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Discover all data sources in a Bedrock Knowledge Base.

    Args:
        kb_id: Knowledge Base ID
        bedrock_agent_client: Optional boto3 bedrock-agent client

    Returns:
        List of data source configurations with details

    Raises:
        ValidationError: If KB doesn't exist or API call fails
    """
    if not bedrock_agent_client:
        bedrock_agent_client = boto3.client("bedrock-agent")

    try:
        data_sources = []
        next_token = None

        # Handle pagination
        while True:
            list_params = {
                "knowledgeBaseId": kb_id,
                "maxResults": 100,  # Maximum allowed
            }
            if next_token:
                list_params["nextToken"] = next_token

            response = bedrock_agent_client.list_data_sources(**list_params)

            for ds_summary in response.get("dataSourceSummaries", []):
                # Get detailed configuration for each data source
                ds_detail = bedrock_agent_client.get_data_source(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds_summary["dataSourceId"],
                )

                data_source = ds_detail.get("dataSource", {})

                # Extract S3 configuration
                s3_config = extract_s3_configuration(data_source)

                data_sources.append(
                    {
                        "dataSourceId": data_source.get("dataSourceId"),
                        "name": data_source.get("name"),
                        "description": data_source.get("description", ""),
                        "status": data_source.get("status"),
                        "s3Bucket": s3_config.get("bucket"),
                        "s3Prefix": s3_config.get("prefix", ""),
                        "createdAt": data_source.get("createdAt"),
                        "updatedAt": data_source.get("updatedAt"),
                    }
                )

            # Check for more pages
            next_token = response.get("nextToken")
            if not next_token:
                break

        logger.info(f"Discovered {len(data_sources)} data sources in KB {kb_id}")

        return data_sources

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            raise ValidationError(
                f"Knowledge Base '{kb_id}' not found. " f"Please verify the KB ID in the AWS Bedrock console."
            )
        elif error_code == "AccessDeniedException":
            raise ValidationError(
                f"Access denied to Knowledge Base '{kb_id}'. "
                f"Please check IAM permissions for bedrock:ListDataSources and bedrock:GetDataSource."
            )
        elif error_code == "ThrottlingException":
            raise ValidationError(
                f"Rate limit exceeded while discovering data sources for KB '{kb_id}'. " f"Please try again later."
            )
        else:
            raise ValidationError(f"Failed to discover data sources: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error discovering data sources for KB {kb_id}: {str(e)}", exc_info=True)
        raise ValidationError(f"Unexpected error discovering data sources: {str(e)}")


def extract_s3_configuration(data_source: Dict[str, Any]) -> Dict[str, str]:
    """Extract S3 bucket and prefix from data source configuration.

    Args:
        data_source: Data source configuration dictionary

    Returns:
        Dictionary with 'bucket' and 'prefix' keys
    """
    data_source_config = data_source.get("dataSourceConfiguration", {})
    s3_config = data_source_config.get("s3Configuration", {})

    # Extract bucket from ARN (format: arn:aws:s3:::bucket-name)
    bucket_arn = s3_config.get("bucketArn", "")
    bucket = bucket_arn.split(":::")[-1] if bucket_arn else ""

    # Get first inclusion prefix if available
    inclusion_prefixes = s3_config.get("inclusionPrefixes", [])
    prefix = inclusion_prefixes[0] if inclusion_prefixes else ""

    return {"bucket": bucket, "prefix": prefix}


def build_pipeline_configs_from_kb_config(
    kb_config: Any,
) -> List[Dict[str, Any]]:
    """Build PipelineConfigs from BedrockKnowledgeBaseConfig.

    Args:
        kb_config: BedrockKnowledgeBaseConfig object with knowledgeBaseId and dataSources array

    Returns:
        List of PipelineConfig dictionaries

    Raises:
        ValidationError: If duplicate data source IDs or S3 URIs found
    """

    pipeline_configs = []
    data_source_ids = set()
    s3_uris = set()

    # Extract data sources (handle both dict and object)
    if isinstance(kb_config, dict):
        data_sources = kb_config.get("dataSources", [])
    else:
        data_sources = kb_config.dataSources

    for data_source in data_sources:
        # Extract fields (handle both dict and object)
        if isinstance(data_source, dict):
            data_source_id = data_source.get("id")
            s3_uri = data_source.get("s3Uri")
        else:
            data_source_id = data_source.id
            s3_uri = data_source.s3Uri

        # Validate required fields
        if not data_source_id:
            raise ValidationError("Data source ID is required")
        if not s3_uri:
            raise ValidationError("S3 URI is required")
        if not s3_uri.startswith("s3://"):
            raise ValidationError(f"Invalid S3 URI format: {s3_uri}")

        # Check for duplicate data source IDs
        if data_source_id in data_source_ids:
            raise ValidationError(f"Duplicate data source ID: {data_source_id}")
        data_source_ids.add(data_source_id)

        # Check for duplicate S3 URIs
        if s3_uri in s3_uris:
            raise ValidationError(f"Duplicate S3 URI: {s3_uri}")
        s3_uris.add(s3_uri)

        # Parse S3 URI (s3://bucket/prefix)
        s3_parts = s3_uri[5:].split("/", 1)  # Remove s3:// and split
        s3_bucket = s3_parts[0]
        s3_prefix = s3_parts[1] if len(s3_parts) > 1 else ""

        # Build pipeline config with collectionId set to dataSourceId
        pipeline_config = {
            "s3Bucket": s3_bucket,
            "s3Prefix": s3_prefix,
            "collectionId": data_source_id,  # Use data source ID as collection ID
            "trigger": PipelineTrigger.EVENT,
            "autoRemove": True,
            "chunkingStrategy": NoneChunkingStrategy(type=ChunkingStrategyType.NONE),
        }
        pipeline_configs.append(pipeline_config)

    logger.info(f"Built {len(pipeline_configs)} pipeline configs from {len(data_sources)} data sources")
    return pipeline_configs


def get_available_data_sources(
    kb_id: str,
    repository_id: Optional[str] = None,
    bedrock_agent_client: Optional[Any] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Get all data sources for a Knowledge Base.

    Args:
        kb_id: Knowledge Base ID
        repository_id: Optional repository ID (unused, for API compatibility)
        bedrock_agent_client: Optional boto3 bedrock-agent client

    Returns:
        Tuple of (all_data_sources, empty_list)

    Raises:
        ValidationError: If KB doesn't exist or API call fails
    """
    # Get all data sources for the KB
    all_data_sources = discover_kb_data_sources(
        kb_id=kb_id,
        bedrock_agent_client=bedrock_agent_client,
    )

    logger.info(f"Found {len(all_data_sources)} data sources for KB {kb_id}")

    return all_data_sources
