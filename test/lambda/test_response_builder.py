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

"""Unit tests for response_builder module."""

import json
from datetime import datetime
from decimal import Decimal

from utilities.response_builder import DecimalEncoder, generate_exception_response, generate_html_response


class TestDecimalEncoder:
    """Test DecimalEncoder class."""

    def test_encode_decimal(self):
        """Test DecimalEncoder handles Decimal objects."""
        obj = {"price": Decimal("123.45"), "quantity": Decimal("10")}
        result = json.dumps(obj, cls=DecimalEncoder)
        parsed = json.loads(result)

        assert parsed["price"] == 123.45
        assert parsed["quantity"] == 10.0

    def test_encode_datetime(self):
        """Test DecimalEncoder handles datetime objects."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        obj = {"timestamp": dt}
        result = json.dumps(obj, cls=DecimalEncoder)

        assert "2025-01-15T10:30:45" in result

    def test_encode_mixed_types(self):
        """Test DecimalEncoder handles mixed types."""
        obj = {
            "decimal_value": Decimal("99.99"),
            "datetime_value": datetime(2025, 1, 1),
            "string_value": "test",
            "int_value": 42,
        }
        result = json.dumps(obj, cls=DecimalEncoder)
        parsed = json.loads(result)

        assert parsed["decimal_value"] == 99.99
        assert "2025-01-01" in result
        assert parsed["string_value"] == "test"
        assert parsed["int_value"] == 42


class TestGenerateHtmlResponse:
    """Test generate_html_response function."""

    def test_success_response(self):
        """Test generate_html_response creates proper success response."""
        response = generate_html_response(200, {"message": "success", "data": {"id": "123"}})

        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

        body = json.loads(response["body"])
        assert body["message"] == "success"
        assert body["data"]["id"] == "123"

    def test_security_headers(self):
        """Test generate_html_response includes security headers."""
        response = generate_html_response(200, {})

        headers = response["headers"]
        assert headers["Strict-Transport-Security"] == "max-age:47304000; includeSubDomains"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Cache-Control"] == "no-store, no-cache"
        assert headers["Pragma"] == "no-cache"

    def test_error_response(self):
        """Test generate_html_response creates proper error response."""
        response = generate_html_response(404, {"error": "Not Found", "message": "Resource not found"})

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error"] == "Not Found"
        assert body["message"] == "Resource not found"

    def test_with_decimal_values(self):
        """Test generate_html_response handles Decimal values."""
        response = generate_html_response(200, {"price": Decimal("19.99")})

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["price"] == 19.99


class TestGenerateExceptionResponse:
    """Test generate_exception_response function."""

    def test_validation_error(self):
        """Test generate_exception_response with ValidationError."""

        class ValidationError(Exception):
            pass

        error = ValidationError("Invalid input format")
        response = generate_exception_response(error)

        assert response["statusCode"] == 400
        assert "Invalid input format" in response["body"]

    def test_aws_sdk_error(self):
        """Test generate_exception_response with AWS SDK error."""
        error = Exception("DynamoDB error")
        error.response = {"ResponseMetadata": {"HTTPStatusCode": 403}}  # type: ignore

        response = generate_exception_response(error)

        assert response["statusCode"] == 403
        assert "DynamoDB error" in response["body"]

    def test_custom_http_status_code(self):
        """Test generate_exception_response with http_status_code attribute."""
        error = Exception("Custom error")
        error.http_status_code = 404  # type: ignore
        error.message = "Resource not found"  # type: ignore

        response = generate_exception_response(error)

        assert response["statusCode"] == 404
        assert "Resource not found" in response["body"]

    def test_custom_status_code(self):
        """Test generate_exception_response with status_code attribute."""
        error = Exception("Another error")
        error.status_code = 409  # type: ignore
        error.message = "Conflict detected"  # type: ignore

        response = generate_exception_response(error)

        assert response["statusCode"] == 409
        assert "Conflict detected" in response["body"]

    def test_missing_request_context(self):
        """Test generate_exception_response with missing requestContext."""
        error = KeyError("requestContext")

        response = generate_exception_response(error)

        assert response["statusCode"] == 400
        assert "requestContext" in response["body"]

    def test_missing_path_parameters(self):
        """Test generate_exception_response with missing pathParameters."""
        error = KeyError("pathParameters")

        response = generate_exception_response(error)

        assert response["statusCode"] == 400
        assert "pathParameters" in response["body"]

    def test_generic_exception(self):
        """Test generate_exception_response with generic exception."""
        error = Exception("Something went wrong")

        response = generate_exception_response(error)

        assert response["statusCode"] == 500
        assert "An unexpected error occurred" in response["body"]

    def test_exception_without_response_metadata(self):
        """Test generate_exception_response with AWS error missing metadata."""
        error = Exception("AWS error")
        error.response = {}  # type: ignore

        response = generate_exception_response(error)

        assert response["statusCode"] == 400
        assert "AWS error" in response["body"]
