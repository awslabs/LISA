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

"""Lambda functions for managing MCP Tools in AWS S3."""
import json
import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
import botocore.exceptions
from pydantic import BaseModel, Field
from utilities.auth import is_admin
from utilities.common_functions import api_wrapper, retry_config
from utilities.exceptions import HTTPException

from .syntax_validator import PythonSyntaxValidator

logger = logging.getLogger(__name__)

# Initialize the S3 resource using environment variables
s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
WORKBENCH_BUCKET = os.environ.get("WORKBENCH_BUCKET", "")

MCPWORKBENCH_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "LISA_MCP_WORKBENCH"))


class MCPToolModel(BaseModel):
    """A Pydantic model representing an MCP Tool."""

    # The filename/toolId seen by frontend
    id: str

    # The Python code content
    contents: str

    # Timestamp of when the tool was created/updated
    updated_at: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())

    @property
    def s3_key(self) -> str:
        """Get the S3 key for this tool."""
        # Ensure the id ends with .py
        if not self.id.endswith(".py"):
            return f"{self.id}.py"
        return self.id


def _get_tool_from_s3(tool_id: str) -> MCPToolModel:
    """Helper function to retrieve a tool from S3."""
    # Ensure the tool_id ends with .py
    if not tool_id.endswith(".py"):
        tool_id = f"{tool_id}.py"

    try:
        response = s3_client.get_object(Bucket=WORKBENCH_BUCKET, Key=tool_id)
        contents = response["Body"].read().decode("utf-8")
        return MCPToolModel(
            id=tool_id,
            contents=contents,
            updated_at=response.get("LastModified", datetime.now()).isoformat(),
        )
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, message=f"Tool {tool_id} not found in S3 bucket.") from e
        # Log and re-raise as ValueError to keep the function's contract
        logger.error("Error retrieving tool from S3: %s", e, exc_info=True)
        raise ValueError(f"Failed to retrieve tool: {e}") from e
    except Exception as e:
        logger.error("Unexpected error retrieving tool from S3: %s", e, exc_info=True)
        raise ValueError(f"Failed to retrieve tool: {e}") from e


@api_wrapper
def read(event: dict, context: dict) -> Any:
    """Retrieve a specific tool from S3."""
    if not is_admin(event):
        raise ValueError("Only admin users can access tools.")

    tool_id = event.get("pathParameters", {}).get("toolId")
    if not tool_id:
        raise ValueError("Missing toolId parameter.")

    logger.info(f"Reading tool with ID: {tool_id}")

    try:
        tool = _get_tool_from_s3(tool_id)
        return tool.model_dump()
    except HTTPException:
        # Let HTTPException pass through for proper status codes
        raise
    except ValueError as e:
        # This is likely from _get_tool_from_s3 already properly formatted
        raise e
    except Exception as e:
        logger.error("Unexpected error reading tool: %s", e, exc_info=True)
        raise ValueError(f"Failed to read tool: {e}") from e


@api_wrapper
def list(event: dict, context: dict) -> Dict[str, Any]:
    """List all tools from S3."""
    if not is_admin(event):
        raise ValueError("Only admin users can access tools.")

    try:
        response = s3_client.list_objects_v2(Bucket=WORKBENCH_BUCKET, Prefix="")

        tools = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            # Only include Python files
            if key.endswith(".py"):
                # We exclude the actual contents for the list operation to save bandwidth
                tools.append(
                    {
                        "id": key,
                        "updated_at": obj.get("LastModified", datetime.now()).isoformat(),
                        "size": obj.get("Size", 0),
                    }
                )

        return {"tools": tools}
    except botocore.exceptions.ClientError as e:
        logger.error("Error listing tools from S3: %s", e, exc_info=True)
        raise ValueError(f"Failed to list tools: {e}") from e
    except Exception as e:
        logger.error("Unexpected error listing tools: %s", e, exc_info=True)
        raise ValueError(f"Failed to list tools: {e}") from e


@api_wrapper
def create(event: dict, context: dict) -> Any:
    """Create a new tool in S3."""
    if not is_admin(event):
        raise ValueError("Only admin users can access tools.")

    try:
        body = json.loads(event["body"], parse_float=Decimal)

        # Ensure the required fields are present
        if "id" not in body or "contents" not in body:
            raise ValueError("Missing required fields: 'id' and 'contents' are required.")

        # Create the tool model
        tool_model = MCPToolModel(id=body["id"], contents=body["contents"])

        # Upload to S3
        s3_client.put_object(
            Bucket=WORKBENCH_BUCKET,
            Key=tool_model.s3_key,
            Body=tool_model.contents.encode("utf-8"),
            ContentType="text/x-python",
        )

        return tool_model.model_dump()
    except botocore.exceptions.ClientError as e:
        logger.error("Error creating tool in S3: %s", e, exc_info=True)
        raise ValueError(f"Failed to create tool: {e}") from e
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in request body: %s", e, exc_info=True)
        raise ValueError(f"Invalid request body: {e}") from e
    except Exception as e:
        logger.error("Unexpected error creating tool: %s", e, exc_info=True)
        raise ValueError(f"Failed to create tool: {e}") from e


@api_wrapper
def update(event: dict, context: dict) -> Any:
    """Update an existing tool in S3."""
    if not is_admin(event):
        raise ValueError("Only admin users can access tools.")

    try:
        tool_id = event.get("pathParameters", {}).get("toolId")
        if not tool_id:
            raise ValueError("Missing toolId parameter.")

        body = json.loads(event["body"], parse_float=Decimal)

        # Ensure the contents field is present
        if "contents" not in body:
            raise ValueError("Missing required field: 'contents' is required.")

        # Check if the tool exists
        try:
            _get_tool_from_s3(tool_id)
        except HTTPException:
            raise HTTPException(status_code=404, message=f"Tool {tool_id} does not exist.")

        # Create updated tool model
        tool_model = MCPToolModel(id=tool_id, contents=body["contents"])

        # Update in S3
        s3_client.put_object(
            Bucket=WORKBENCH_BUCKET,
            Key=tool_model.s3_key,
            Body=tool_model.contents.encode("utf-8"),
            ContentType="text/x-python",
        )

        return tool_model.model_dump()
    except botocore.exceptions.ClientError as e:
        logger.error("Error updating tool in S3: %s", e, exc_info=True)
        raise ValueError(f"Failed to update tool: {e}") from e
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in request body: %s", e, exc_info=True)
        raise ValueError(f"Invalid request body: {e}") from e
    except Exception as e:
        logger.error("Unexpected error updating tool: %s", e, exc_info=True)
        raise ValueError(f"Failed to update tool: {e}") from e


@api_wrapper
def delete(event: dict, context: dict) -> Dict[str, str]:
    """Delete a tool from S3."""
    if not is_admin(event):
        raise ValueError("Only admin users can access tools.")

    try:
        tool_id = event.get("pathParameters", {}).get("toolId")
        if not tool_id:
            raise ValueError("Missing toolId parameter.")

        # Ensure the tool_id ends with .py
        if not tool_id.endswith(".py"):
            tool_id = f"{tool_id}.py"

        # Check if the tool exists before deletion
        try:
            _get_tool_from_s3(tool_id)
        except HTTPException:
            raise HTTPException(status_code=404, message=f"Tool {tool_id} does not exist.")

        # Delete from S3
        s3_client.delete_object(Bucket=WORKBENCH_BUCKET, Key=tool_id)

        return {"status": "ok", "message": f"Tool {tool_id} deleted successfully."}
    except botocore.exceptions.ClientError as e:
        logger.error("Error deleting tool from S3: %s", e, exc_info=True)
        raise ValueError(f"Failed to delete tool: {e}") from e
    except Exception as e:
        logger.error("Unexpected error deleting tool: %s", e, exc_info=True)
        raise ValueError(f"Failed to delete tool: {e}") from e


@api_wrapper
def validate_syntax(event: dict, context: dict) -> Dict[str, Any]:
    """Validate Python code syntax without execution."""
    if not is_admin(event):
        raise ValueError("Only admin users can validate code syntax.")

    try:
        body = json.loads(event["body"], parse_float=Decimal)

        # Ensure the required field is present
        if "code" not in body:
            raise ValueError("Missing required field: 'code' is required.")

        code = body["code"]
        if not isinstance(code, str):
            raise ValueError("Code must be a string.")

        logger.info("Validating Python code syntax")

        # Initialize the validator and validate the code
        validator = PythonSyntaxValidator()
        result = validator.validate_code(code)

        # Convert the dataclass to a dictionary for JSON serialization
        response = {
            "is_valid": result.is_valid,
            "syntax_errors": result.syntax_errors,
            "missing_required_imports": result.missing_required_imports,
            "validation_timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Validation completed. Valid: {result.is_valid}, " f"Errors: {len(result.syntax_errors)}")

        return response

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in request body: %s", e, exc_info=True)
        raise ValueError(f"Invalid request body: {e}") from e
    except Exception as e:
        logger.error("Unexpected error validating syntax: %s", e, exc_info=True)
        raise ValueError(f"Failed to validate syntax: {e}") from e
