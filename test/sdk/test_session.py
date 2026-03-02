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

"""Unit tests for SessionMixin."""

import pytest
import responses
from lisapy import LisaApi


class TestSessionMixin:
    """Test suite for session-related operations."""

    @responses.activate
    def test_list_sessions(self, lisa_api: LisaApi, api_url: str, mock_sessions_response: list):
        """Test listing all sessions."""
        responses.add(responses.GET, f"{api_url}/session", json=mock_sessions_response, status=200)

        sessions = lisa_api.list_sessions()

        assert len(sessions) == 2
        assert sessions[0]["sessionId"] == "sess-123"
        assert sessions[1]["userId"] == "user-1"

    @responses.activate
    def test_list_sessions_empty(self, lisa_api: LisaApi, api_url: str):
        """Test listing sessions when none exist."""
        responses.add(responses.GET, f"{api_url}/session", json=[], status=200)

        sessions = lisa_api.list_sessions()

        assert len(sessions) == 0
        assert isinstance(sessions, list)

    @responses.activate
    def test_get_session_by_user(self, lisa_api: LisaApi, api_url: str):
        """Test getting session for current user."""
        user_session = {
            "sessionId": "sess-current",
            "userId": "current-user",
            "createdAt": "2024-01-24T10:00:00Z",
            "lastAccessedAt": "2024-01-24T14:30:00Z",
        }

        responses.add(responses.GET, f"{api_url}/session", json=user_session, status=200)

        session = lisa_api.get_session_by_user()

        assert session["sessionId"] == "sess-current"
        assert session["userId"] == "current-user"

    @responses.activate
    def test_list_sessions_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when listing sessions fails."""
        responses.add(responses.GET, f"{api_url}/session", json={"error": "Unauthorized"}, status=401)

        with pytest.raises(Exception):
            lisa_api.list_sessions()

    @responses.activate
    def test_get_session_by_user_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when getting user session fails."""
        responses.add(responses.GET, f"{api_url}/session", json={"error": "Not found"}, status=404)

        with pytest.raises(Exception):
            lisa_api.get_session_by_user()
