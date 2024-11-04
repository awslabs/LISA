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

"""Validation utilities for Lambda functions."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class SecurityError(Exception):
    """Custom exception for security-related errors."""

    pass


def validate_model_name(model_name: str) -> bool:
    """Validate model name is a non-empty string.

    Args:
        model_name: Name of the model to validate

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If model name is invalid
    """
    if not isinstance(model_name, str):
        raise ValidationError("Model name must be a string")

    if not model_name or model_name.isspace():
        raise ValidationError("Model name cannot be empty")

    return True


def validate_repository_type(repo_type: str) -> bool:
    """Validate repository type against allowed types.

    Args:
        repo_type: Repository type to validate

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If repository type is invalid
    """
    ALLOWED_TYPES = ["opensearch", "pgvector"]

    if not isinstance(repo_type, str):
        raise ValidationError("Repository type must be a string")

    if repo_type not in ALLOWED_TYPES:
        raise ValidationError(f"Invalid repository type. Must be one of: {ALLOWED_TYPES}")

    return True


def validate_s3_key(key: str) -> bool:
    """Validate S3 key format and allowed extensions.

    Args:
        key: S3 key to validate

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If key is invalid
    """
    ALLOWED_EXTENSIONS = [".txt", ".pdf", ".docx"]

    if not isinstance(key, str):
        raise ValidationError("S3 key must be a string")

    if not key or key.isspace():
        raise ValidationError("S3 key cannot be empty")

    if not any(key.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise ValidationError(f"Invalid file type. Must be one of: {ALLOWED_EXTENSIONS}")

    # Basic path traversal check
    if ".." in key:
        raise SecurityError("Path traversal detected in S3 key")

    return True


def validate_chunk_params(chunk_size: Optional[int], chunk_overlap: Optional[int]) -> bool:
    """
    Validate chunking parameters.

    Args:
        chunk_size: Size of chunks
        chunk_overlap: Overlap between chunks

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If parameters are invalid
    """
    if chunk_size is not None:
        if not isinstance(chunk_size, int):
            raise ValidationError("Chunk size must be an integer")

        if chunk_size < 100 or chunk_size > 10000:
            raise ValidationError("Chunk size must be between 100 and 10000")

    if chunk_overlap is not None:
        if not isinstance(chunk_overlap, int):
            raise ValidationError("Chunk overlap must be an integer")

        if chunk_overlap < 0:
            raise ValidationError("Chunk overlap cannot be negative")

        if chunk_size and chunk_overlap >= chunk_size:
            raise ValidationError("Chunk overlap must be less than chunk size")

    return True


def safe_error_response(error: Exception) -> dict:
    """Create a safe error response that doesn't leak implementation details.

    Args:
        error: The exception that occurred

    Returns:
        dict: Sanitized error response
    """
    if isinstance(error, ValidationError):
        return {"statusCode": 400, "body": {"message": str(error)}}
    elif isinstance(error, SecurityError):
        return {"statusCode": 403, "body": {"message": "Security validation failed"}}
    else:
        # Log the full error internally but return generic message
        logger.error(f"Internal error: {str(error)}", exc_info=True)
        return {"statusCode": 500, "body": {"message": "Internal server error"}}
