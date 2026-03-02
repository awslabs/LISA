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

"""Unit tests for DocsMixin."""

import pytest
import responses
from lisapy import LisaApi


class TestDocsMixin:
    """Test suite for docs-related operations."""

    @responses.activate
    def test_list_docs(self, lisa_api: LisaApi, api_url: str):
        """Test getting API documentation."""
        swagger_html = """
        <!DOCTYPE html>
        <html>
        <head><title>LISA API Documentation</title></head>
        <body>
            <h1>LISA REST API</h1>
            <p>API documentation for LISA</p>
        </body>
        </html>
        """

        responses.add(responses.GET, f"{api_url}/docs", body=swagger_html, status=200, content_type="text/html")

        docs = lisa_api.list_docs()

        assert "LISA API Documentation" in docs
        assert "LISA REST API" in docs
        assert len(docs) > 0

    @responses.activate
    def test_list_docs_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when getting docs fails."""
        responses.add(responses.GET, f"{api_url}/docs", body="Not Found", status=404)

        with pytest.raises(Exception):
            lisa_api.list_docs()
