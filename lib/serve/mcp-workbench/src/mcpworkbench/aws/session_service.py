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

from __future__ import annotations

from dataclasses import dataclass

from .session_models import AwsSessionRecord
from .session_store import InMemoryAwsSessionStore


class AwsSessionMissingError(Exception):
    """Raised when no AWS session is stored for the given user/session."""


class AwsSessionExpiredError(Exception):
    """Raised when an AWS session exists but is expired."""


@dataclass
class AwsSessionService:
    """High-level helper for retrieving AWS sessions for MCP tools."""

    store: InMemoryAwsSessionStore

    def get_aws_session_for_user(self, user_id: str, session_id: str) -> AwsSessionRecord:
        record = self.store.get_session(user_id, session_id)
        if record is None:
            # We intentionally don't distinguish missing vs expired here since
            # InMemoryAwsSessionStore cleans up expired records on access.
            raise AwsSessionMissingError("AWS session not connected or expired.")
        return record
