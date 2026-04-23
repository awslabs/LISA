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

import logging
import os
from typing import Any, TYPE_CHECKING

import boto3
import botocore.exceptions
from lisa.utilities.auth import is_admin
from lisa.utilities.common_functions import api_wrapper, retry_config
from lisa.utilities.exceptions import (
    BadRequestException,
    ForbiddenException,
    InternalServerErrorException,
    NotFoundException,
)
from lisa.utilities.time import iso_string
from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    from .syntax_validator import PythonSyntaxValidator
else:
    try:
        # When imported as a package in unit tests (`mcp_workbench.lambda_functions`)
        from .syntax_validator import PythonSyntaxValidator
    except ImportError:  # pragma: no cover
        # When deployed in Lambda, handler files are at the zip root and `lambda_functions`
        # is not part of a package.
        from syntax_validator import PythonSyntaxValidator

logger = logging.getLogger(__name__)

# Initialize the S3 resource using environment variables
s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
WORKBENCH_BUCKET = os.environ.get("WORKBENCH_BUCKET", "")

from lisa.mcp.workbench import MCPWORKBENCH_UUID  # noqa: E402,F401  (re-export for callers)


class MCPToolModel(BaseModel):
    """A Pydantic model representing an MCP Tool."""

    # The filename/toolId seen by frontend
    id: str

    # The Python code content
    contents: str

    # Timestamp of when the tool was created/updated
    updated_at: str | None = Field(default_factory=iso_string)

    @property
    def s3_key(self) -> str:
        """Get the S3 key for this tool."""
        # Ensure the id ends with .py
        if not self.id.endswith(".py"):
            return f"{self.id}.py"
        return self.id


class MCPToolUpdateModel(BaseModel):
    """A Pydantic model for updating an MCP Tool (id comes from path parameters)."""

    contents: str


class ValidateSyntaxRequest(BaseModel):
    """Request model for Python syntax validation."""

    code: str


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
            updated_at=response.get("LastModified").isoformat() if response.get("LastModified") else iso_string(),
        )
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404"):
            raise NotFoundException(f"Tool {tool_id} not found in S3 bucket.") from e
        logger.error("Error retrieving tool from S3: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to retrieve tool: {e}") from e
    except Exception as e:
        logger.error("Unexpected error retrieving tool from S3: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to retrieve tool: {e}") from e


@api_wrapper
def read(event: dict, context: dict) -> Any:
    """Retrieve a specific tool from S3."""
    if not is_admin(event):
        raise ForbiddenException("Only admin users can access tools.")

    tool_id = event.get("pathParameters", {}).get("toolId")
    if not tool_id:
        raise BadRequestException("Missing toolId parameter.")

    logger.info(f"Reading tool with ID: {tool_id}")

    try:
        tool = _get_tool_from_s3(tool_id)
        return tool.model_dump()
    except (NotFoundException, ForbiddenException, BadRequestException, InternalServerErrorException):
        raise
    except Exception as e:
        logger.error("Unexpected error reading tool: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to read tool: {e}") from e


@api_wrapper
def list(event: dict, context: dict) -> dict[str, Any]:
    """List all tools from S3."""
    if not is_admin(event):
        raise ForbiddenException("Only admin users can access tools.")

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
                        "updated_at": obj.get("LastModified").isoformat() if obj.get("LastModified") else iso_string(),
                        "size": obj.get("Size", 0),
                    }
                )

        return {"tools": tools}
    except botocore.exceptions.ClientError as e:
        logger.error("Error listing tools from S3: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to list tools: {e}") from e
    except Exception as e:
        logger.error("Unexpected error listing tools: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to list tools: {e}") from e


@api_wrapper
def create(event: dict, context: dict) -> Any:
    """Create a new tool in S3."""
    if not is_admin(event):
        raise ForbiddenException("Only admin users can access tools.")

    try:
        tool_model = MCPToolModel.model_validate_json(event["body"])

        # Upload to S3
        s3_client.put_object(
            Bucket=WORKBENCH_BUCKET,
            Key=tool_model.s3_key,
            Body=tool_model.contents.encode("utf-8"),
            ContentType="text/x-python",
        )

        return tool_model.model_dump()
    except ValidationError as e:
        raise BadRequestException(f"Missing required fields: {e}") from e
    except botocore.exceptions.ClientError as e:
        logger.error("Error creating tool in S3: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to create tool: {e}") from e
    except (NotFoundException, ForbiddenException, BadRequestException, InternalServerErrorException):
        raise
    except Exception as e:
        logger.error("Unexpected error creating tool: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to create tool: {e}") from e


@api_wrapper
def update(event: dict, context: dict) -> Any:
    """Update an existing tool in S3."""
    if not is_admin(event):
        raise ForbiddenException("Only admin users can access tools.")

    try:
        tool_id = event.get("pathParameters", {}).get("toolId")
        if not tool_id:
            raise BadRequestException("Missing toolId parameter.")

        update_model = MCPToolUpdateModel.model_validate_json(event["body"])

        # Check if the tool exists (will raise NotFoundException if not found)
        _get_tool_from_s3(tool_id)

        # Build the full tool model using the path parameter id
        tool_model = MCPToolModel(id=tool_id, contents=update_model.contents)

        # Update in S3
        s3_client.put_object(
            Bucket=WORKBENCH_BUCKET,
            Key=tool_model.s3_key,
            Body=tool_model.contents.encode("utf-8"),
            ContentType="text/x-python",
        )

        return tool_model.model_dump()
    except ValidationError as e:
        raise BadRequestException("Missing required field: 'contents'") from e
    except (NotFoundException, ForbiddenException, BadRequestException, InternalServerErrorException):
        raise
    except botocore.exceptions.ClientError as e:
        logger.error("Error updating tool in S3: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to update tool: {e}") from e
    except Exception as e:
        logger.error("Unexpected error updating tool: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to update tool: {e}") from e


@api_wrapper
def delete(event: dict, context: dict) -> dict[str, str]:
    """Delete a tool from S3."""
    if not is_admin(event):
        raise ForbiddenException("Only admin users can access tools.")

    try:
        tool_id = event.get("pathParameters", {}).get("toolId")
        if not tool_id:
            raise BadRequestException("Missing toolId parameter.")

        # Ensure the tool_id ends with .py
        if not tool_id.endswith(".py"):
            tool_id = f"{tool_id}.py"

        # Check if the tool exists before deletion (will raise NotFoundException if not found)
        _get_tool_from_s3(tool_id)

        # Delete from S3
        s3_client.delete_object(Bucket=WORKBENCH_BUCKET, Key=tool_id)

        return {"status": "ok", "message": f"Tool {tool_id} deleted successfully."}
    except (NotFoundException, ForbiddenException, BadRequestException, InternalServerErrorException):
        raise
    except botocore.exceptions.ClientError as e:
        logger.error("Error deleting tool from S3: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to delete tool: {e}") from e
    except Exception as e:
        logger.error("Unexpected error deleting tool: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to delete tool: {e}") from e


@api_wrapper
def validate_syntax(event: dict, context: dict) -> dict[str, Any]:
    """Validate Python code syntax without execution."""
    if not is_admin(event):
        raise ForbiddenException("Only admin users can validate code syntax.")

    try:
        request = ValidateSyntaxRequest.model_validate_json(event["body"])

        logger.info("Validating Python code syntax")

        # Initialize the validator and validate the code
        validator = PythonSyntaxValidator()
        result = validator.validate_code(request.code)

        # Convert the dataclass to a dictionary for JSON serialization
        response = {
            "is_valid": result.is_valid,
            "syntax_errors": result.syntax_errors,
            "missing_required_imports": result.missing_required_imports,
            "validation_timestamp": iso_string(),
        }

        logger.info(f"Validation completed. Valid: {result.is_valid}, " f"Errors: {len(result.syntax_errors)}")

        return response

    except ValidationError as e:
        raise BadRequestException(f"Invalid request body: {e}") from e
    except (NotFoundException, ForbiddenException, BadRequestException, InternalServerErrorException):
        raise
    except Exception as e:
        logger.error("Unexpected error validating syntax: %s", e, exc_info=True)
        raise InternalServerErrorException(f"Failed to validate syntax: {e}") from e
