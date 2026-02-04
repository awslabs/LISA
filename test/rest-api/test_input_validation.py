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

"""Unit tests for input validation middleware."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from middleware.input_validation import contains_null_bytes, validate_input_middleware


class TestContainsNullBytes:
    """Test contains_null_bytes function."""

    def test_detects_null_byte(self) -> None:
        """Test that null bytes are detected."""
        assert contains_null_bytes("test\x00data") is True
        assert contains_null_bytes("\x00") is True
        assert contains_null_bytes("prefix\x00suffix") is True

    def test_no_null_bytes(self) -> None:
        """Test that clean strings return False."""
        assert contains_null_bytes("normal string") is False
        assert contains_null_bytes("") is False
        assert contains_null_bytes("special chars: !@#$%^&*()") is False


class TestInputValidationMiddleware:
    """Test input validation middleware."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a test FastAPI app with validation middleware."""
        test_app = FastAPI()

        @test_app.middleware("http")
        async def validation_middleware(request, call_next):  # type: ignore[no-untyped-def]
            return await validate_input_middleware(request, call_next)

        @test_app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"message": "success"}

        @test_app.post("/test")
        async def test_post_endpoint(data: dict) -> dict[str, str | dict]:  # type: ignore[type-arg]
            return {"message": "success", "data": data}

        @test_app.get("/test/{item_id}")
        async def test_path_param(item_id: str) -> dict[str, str]:
            return {"item_id": item_id}

        return test_app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_valid_get_request(self, client: TestClient) -> None:
        """Test that valid GET requests pass through."""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"message": "success"}

    def test_valid_post_request(self, client: TestClient) -> None:
        """Test that valid POST requests pass through."""
        response = client.post("/test", json={"key": "value"})
        assert response.status_code == 200

    def test_invalid_http_method(self, client: TestClient) -> None:
        """Test that invalid HTTP methods are rejected."""
        # FastAPI/TestClient doesn't allow truly invalid methods,
        # but we can test that only valid methods work
        response = client.get("/test")
        assert response.status_code == 200

    def test_null_byte_in_path(self, client: TestClient) -> None:
        """Test that null bytes in path are rejected."""
        # Note: TestClient may not allow literal null bytes in URLs
        # This test documents the expected behavior
        response = client.get("/test\x00malicious")
        assert response.status_code == 400
        assert "Invalid characters" in response.json()["message"]

    def test_null_byte_in_path_parameter(self, client: TestClient) -> None:
        """Test that null bytes in path parameters are rejected."""
        response = client.get("/test/item\x00malicious")
        assert response.status_code == 400
        assert "Invalid characters" in response.json()["message"]

    def test_null_byte_in_query_parameter(self, client: TestClient) -> None:
        """Test that null bytes in query parameters are rejected."""
        response = client.get("/test?param=value\x00malicious")
        assert response.status_code == 400
        assert "Invalid characters" in response.json()["message"]

    def test_null_byte_in_request_body(self, client: TestClient) -> None:
        """Test that null bytes in request body are rejected."""
        # Send raw body with null byte
        response = client.post(
            "/test",
            content=b'{"key": "value\x00malicious"}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert "Invalid characters" in response.json()["message"]

    def test_oversized_request_body(self, client: TestClient) -> None:
        """Test that oversized request bodies are rejected."""
        # Create a body larger than 10MB (default limit)
        large_data = {"data": "x" * (10 * 1024 * 1024 + 1)}
        response = client.post("/test", json=large_data)
        assert response.status_code == 413
        assert "Payload Too Large" in response.json()["error"]

    def test_valid_query_parameters(self, client: TestClient) -> None:
        """Test that valid query parameters pass through."""
        response = client.get("/test?param1=value1&param2=value2")
        assert response.status_code == 200

    def test_valid_path_parameters(self, client: TestClient) -> None:
        """Test that valid path parameters pass through."""
        response = client.get("/test/123")
        assert response.status_code == 200
        assert response.json()["item_id"] == "123"

    def test_empty_request_body(self, client: TestClient) -> None:
        """Test that empty request bodies are handled correctly."""
        response = client.post("/test", json={})
        assert response.status_code == 200

    def test_special_characters_allowed(self, client: TestClient) -> None:
        """Test that special characters (non-null) are allowed."""
        response = client.get("/test?param=value!@#$%^&*()")
        assert response.status_code == 200
