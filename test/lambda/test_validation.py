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


import os
import sys

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


def test_validate_model_name_valid():
    """Test validate_model_name with valid model name."""
    from utilities.validation import validate_model_name

    result = validate_model_name("valid-model-123")
    assert result is True


def test_validate_model_name_empty():
    """Test validate_model_name raises ValidationError for empty string."""
    from utilities.validation import validate_model_name, ValidationError

    with pytest.raises(ValidationError, match="Model name cannot be empty"):
        validate_model_name("")


def test_validate_model_name_whitespace():
    """Test validate_model_name raises ValidationError for whitespace."""
    from utilities.validation import validate_model_name, ValidationError

    with pytest.raises(ValidationError, match="Model name cannot be empty"):
        validate_model_name("   ")


def test_validate_model_name_not_string():
    """Test validate_model_name raises ValidationError for non-string."""
    from utilities.validation import validate_model_name, ValidationError

    with pytest.raises(ValidationError, match="Model name must be a string"):
        validate_model_name(123)


def test_safe_error_response_validation_error():
    """Test safe_error_response with ValidationError."""
    from utilities.validation import safe_error_response, ValidationError

    error = ValidationError("Invalid input")
    response = safe_error_response(error)

    assert response["statusCode"] == 400
    assert response["body"]["message"] == "Invalid input"


def test_safe_error_response_security_error():
    """Test safe_error_response with SecurityError."""
    from utilities.validation import safe_error_response, SecurityError

    error = SecurityError("Access denied")
    response = safe_error_response(error)

    assert response["statusCode"] == 403
    assert response["body"]["message"] == "Security validation failed"


def test_safe_error_response_generic_error():
    """Test safe_error_response with generic Exception."""
    from utilities.validation import safe_error_response

    error = Exception("Internal error")
    response = safe_error_response(error)

    assert response["statusCode"] == 500
    assert response["body"]["message"] == "Internal server error"
