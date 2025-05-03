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
