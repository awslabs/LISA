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

"""Validation utilities for Bedrock Knowledge Base operations."""

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)


def validate_bedrock_kb_exists(kb_id: str, bedrock_agent_client: Any | None = None) -> dict[str, Any]:
    """
    Validate that a Bedrock Knowledge Base exists and is accessible.

    Args:
        kb_id: Knowledge Base ID to validate
        bedrock_agent_client: Optional boto3 bedrock-agent client (creates one if not provided)

    Returns:
        Knowledge Base configuration dictionary

    Raises:
        ValidationError: If KB doesn't exist or is not accessible
    """
    if not bedrock_agent_client:
        bedrock_agent_client = boto3.client("bedrock-agent")

    try:
        response = bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
        kb_config = response.get("knowledgeBase", {})

        logger.info(f"Validated Knowledge Base {kb_id}: {kb_config.get('name')}")
        return kb_config  # type: ignore[no-any-return]

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code == "ResourceNotFoundException":
            raise ValidationError(
                f"Knowledge Base '{kb_id}' not found. " f"Please verify the KB ID in the AWS Bedrock console."
            )
        elif error_code == "AccessDeniedException":
            raise ValidationError(
                f"Access denied to Knowledge Base '{kb_id}'. "
                f"Please check IAM permissions for bedrock:GetKnowledgeBase."
            )
        else:
            raise ValidationError(f"Failed to validate Knowledge Base '{kb_id}': {str(e)}")
    except Exception as e:
        raise ValidationError(f"Unexpected error validating Knowledge Base '{kb_id}': {str(e)}")


def validate_data_source_exists(
    kb_id: str, data_source_id: str, bedrock_agent_client: Any | None = None
) -> dict[str, Any]:
    """
    Validate that a data source exists in a Bedrock Knowledge Base.

    Args:
        kb_id: Knowledge Base ID
        data_source_id: Data Source ID to validate
        bedrock_agent_client: Optional boto3 bedrock-agent client

    Returns:
        Data source configuration dictionary

    Raises:
        ValidationError: If data source doesn't exist or is not accessible
    """
    if not bedrock_agent_client:
        bedrock_agent_client = boto3.client("bedrock-agent")

    try:
        response = bedrock_agent_client.get_data_source(knowledgeBaseId=kb_id, dataSourceId=data_source_id)
        data_source_config = response.get("dataSource", {})

        logger.info(f"Validated Data Source {data_source_id} in KB {kb_id}: " f"{data_source_config.get('name')}")
        return data_source_config  # type: ignore[no-any-return]

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code == "ResourceNotFoundException":
            raise ValidationError(
                f"Data Source '{data_source_id}' not found in Knowledge Base '{kb_id}'. "
                f"Please verify the Data Source ID in the AWS Bedrock console."
            )
        elif error_code == "AccessDeniedException":
            raise ValidationError(
                f"Access denied to Data Source '{data_source_id}'. "
                f"Please check IAM permissions for bedrock:GetDataSource."
            )
        else:
            raise ValidationError(f"Failed to validate Data Source '{data_source_id}': {str(e)}")
    except Exception as e:
        raise ValidationError(f"Unexpected error validating Data Source '{data_source_id}': {str(e)}")


def validate_bedrock_kb_repository(
    kb_id: str, data_source_id: str, bedrock_agent_client: Any | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Validate both Knowledge Base and Data Source exist.

    Args:
        kb_id: Knowledge Base ID
        data_source_id: Data Source ID
        bedrock_agent_client: Optional boto3 bedrock-agent client

    Returns:
        Tuple of (kb_config, data_source_config)

    Raises:
        ValidationError: If validation fails
    """
    if not bedrock_agent_client:
        bedrock_agent_client = boto3.client("bedrock-agent")

    # Validate KB exists
    kb_config = validate_bedrock_kb_exists(kb_id, bedrock_agent_client)

    # Validate data source exists
    data_source_config = validate_data_source_exists(kb_id, data_source_id, bedrock_agent_client)

    logger.info(f"Successfully validated Bedrock KB repository: KB={kb_id}, DataSource={data_source_id}")

    return kb_config, data_source_config
