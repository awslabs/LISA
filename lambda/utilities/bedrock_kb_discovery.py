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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)

# Cache for data source discovery (5-minute TTL)
_data_source_cache: Dict[str, Tuple[List[Dict[str, Any]], datetime]] = {}
_cache_ttl = timedelta(minutes=5)


def discover_kb_data_sources(
    kb_id: str,
    bedrock_agent_client: Optional[Any] = None,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Discover all data sources in a Bedrock Knowledge Base.

    Args:
        kb_id: Knowledge Base ID
        bedrock_agent_client: Optional boto3 bedrock-agent client
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        List of data source configurations with details

    Raises:
        ValidationError: If KB doesn't exist or API call fails
    """
    # Check cache first
    if not force_refresh and kb_id in _data_source_cache:
        cached_data, cached_time = _data_source_cache[kb_id]
        if datetime.now(timezone.utc) - cached_time < _cache_ttl:
            logger.info(f"Using cached data sources for KB {kb_id}")
            return cached_data

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

        # Update cache
        _data_source_cache[kb_id] = (data_sources, datetime.now(timezone.utc))

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


def get_available_data_sources(
    kb_id: str,
    repository_id: Optional[str] = None,
    bedrock_agent_client: Optional[Any] = None,
    force_refresh: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Get available and managed data sources for a KB.

    Args:
        kb_id: Knowledge Base ID
        repository_id: Optional repository ID to check for managed data sources
        bedrock_agent_client: Optional boto3 client
        force_refresh: If True, bypass cache

    Returns:
        Tuple of (available_data_sources, managed_data_sources)
    """
    all_data_sources = discover_kb_data_sources(kb_id, bedrock_agent_client, force_refresh)

    if not repository_id:
        # All data sources are available if no repository context
        return all_data_sources, []

    # Check which data sources have collections
    from repository.collection_repo import CollectionRepository

    collection_repo = CollectionRepository()

    try:
        collections, _, _ = collection_repo.list_by_repository(repository_id, page_size=100)
        managed_data_source_ids = {c.dataSourceId for c in collections if hasattr(c, "dataSourceId") and c.dataSourceId}

        available = [ds for ds in all_data_sources if ds["dataSourceId"] not in managed_data_source_ids]
        managed = [ds for ds in all_data_sources if ds["dataSourceId"] in managed_data_source_ids]

        logger.info(
            f"Data source availability for KB {kb_id}: "
            f"available={len(available)}, managed={len(managed)}"
        )

        return available, managed
    except Exception as e:
        logger.error(f"Error checking managed data sources: {str(e)}", exc_info=True)
        # If we can't check managed status, return all as available
        return all_data_sources, []


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
                "Access denied to list Knowledge Bases. "
                "Please check IAM permissions for bedrock:ListKnowledgeBases."
            )
        elif error_code == "ThrottlingException":
            raise ValidationError("Rate limit exceeded while listing Knowledge Bases. " "Please try again later.")
        else:
            raise ValidationError(f"Failed to list Knowledge Bases: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error listing Knowledge Bases: {str(e)}", exc_info=True)
        raise ValidationError(f"Unexpected error listing Knowledge Bases: {str(e)}")


def clear_cache(kb_id: Optional[str] = None) -> None:
    """Clear the data source cache.

    Args:
        kb_id: Optional KB ID to clear specific cache entry. If None, clears all cache.
    """
    global _data_source_cache
    if kb_id:
        _data_source_cache.pop(kb_id, None)
        logger.info(f"Cleared cache for KB {kb_id}")
    else:
        _data_source_cache.clear()
        logger.info("Cleared all data source cache")



def generate_collection_id(data_source_name: str) -> str:
    """Generate a valid collection ID from a data source name.

    Converts the data source name to lowercase, replaces spaces and underscores
    with hyphens, and removes invalid characters.

    Args:
        data_source_name: Data source name to convert

    Returns:
        Valid collection ID (lowercase alphanumeric with hyphens)
    """
    # Convert to lowercase
    collection_id = data_source_name.lower()

    # Replace spaces and underscores with hyphens
    collection_id = collection_id.replace(" ", "-").replace("_", "-")

    # Remove invalid characters (keep only alphanumeric and hyphens)
    collection_id = "".join(c for c in collection_id if c.isalnum() or c == "-")

    # Remove leading/trailing hyphens and collapse multiple hyphens
    collection_id = "-".join(filter(None, collection_id.split("-")))

    # Ensure it's not empty
    if not collection_id:
        collection_id = "collection"

    return collection_id


def build_pipeline_config_from_data_source(
    data_source_id: str,
    s3_bucket: str,
    s3_prefix: str = "",
) -> Dict[str, Any]:
    """Build a PipelineConfig from a data source selection.

    Args:
        data_source_id: Data source ID (used as collection ID)
        s3_bucket: S3 bucket for the data source
        s3_prefix: S3 prefix for the data source

    Returns:
        Dictionary representing a PipelineConfig
    """
    from models.domain_objects import ChunkingStrategyType, NoneChunkingStrategy, PipelineTrigger

    return {
        "s3Bucket": s3_bucket,
        "s3Prefix": s3_prefix,
        "collectionId": data_source_id,  # Use data source ID as collection ID
        "trigger": PipelineTrigger.EVENT,
        "autoRemove": True,
        "chunkingStrategy": NoneChunkingStrategy(type=ChunkingStrategyType.NONE),
    }


def build_pipeline_configs_from_selections(
    data_source_selections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build multiple PipelineConfigs from data source selections.

    Args:
        data_source_selections: List of DataSourceSelection dictionaries with:
            - dataSourceId: Data source ID
            - s3Bucket: S3 bucket
            - s3Prefix: S3 prefix (optional)

    Returns:
        List of PipelineConfig dictionaries

    Raises:
        ValidationError: If duplicate data source IDs or S3 bucket/prefix combinations found
    """
    pipeline_configs = []
    data_source_ids = set()
    s3_locations = set()

    for selection in data_source_selections:
        data_source_id = selection.get("dataSourceId")
        s3_bucket = selection.get("s3Bucket")
        s3_prefix = selection.get("s3Prefix", "")

        # Validate required fields
        if not data_source_id:
            raise ValidationError("Data source ID is required")
        if not s3_bucket:
            raise ValidationError("S3 bucket is required")

        # Check for duplicate data source IDs
        if data_source_id in data_source_ids:
            raise ValidationError(f"Duplicate data source ID: {data_source_id}")
        data_source_ids.add(data_source_id)

        # Check for duplicate S3 locations
        s3_location = (s3_bucket, s3_prefix)
        if s3_location in s3_locations:
            raise ValidationError(f"Duplicate S3 location: s3://{s3_bucket}/{s3_prefix}")
        s3_locations.add(s3_location)

        # Build pipeline config
        pipeline_config = build_pipeline_config_from_data_source(
            data_source_id=data_source_id,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
        )
        pipeline_configs.append(pipeline_config)

    logger.info(f"Built {len(pipeline_configs)} pipeline configs from {len(data_source_selections)} selections")
    return pipeline_configs


def validate_pipeline_configs(pipeline_configs: List[Dict[str, Any]]) -> None:
    """Validate pipeline configurations for duplicates and conflicts.

    Args:
        pipeline_configs: List of pipeline config dictionaries

    Raises:
        ValidationError: If validation fails
    """
    if not pipeline_configs:
        raise ValidationError("At least one pipeline configuration is required")

    collection_ids = set()
    s3_locations = set()

    for config in pipeline_configs:
        # Validate required fields
        if not config.get("s3Bucket"):
            raise ValidationError("Pipeline config missing s3Bucket")
        if not config.get("collectionId"):
            raise ValidationError("Pipeline config missing collectionId")

        # Check for duplicate collection IDs
        collection_id = config["collectionId"]
        if collection_id in collection_ids:
            raise ValidationError(f"Duplicate collection ID: {collection_id}")
        collection_ids.add(collection_id)

        # Check for duplicate S3 locations
        s3_location = (config["s3Bucket"], config.get("s3Prefix", ""))
        if s3_location in s3_locations:
            raise ValidationError(
                f"Duplicate S3 location: s3://{s3_location[0]}/{s3_location[1]}"
            )
        s3_locations.add(s3_location)

    logger.info(f"Validated {len(pipeline_configs)} pipeline configs successfully")
