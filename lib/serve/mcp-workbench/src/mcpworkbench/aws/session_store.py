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

from dataclasses import dataclass, field

from .session_models import AwsSessionRecord


@dataclass
class InMemoryAwsSessionStore:
    """Simple in-process implementation of an AWS session store.

    This is suitable for a single MCP Workbench process. For multi-instance deployments, a distributed store such as
    Redis should be used instead.
    """

    safety_margin_seconds: int = 0

    _sessions: dict[tuple[str, str], AwsSessionRecord] = field(default_factory=dict, init=False)

    def set_session(self, record: AwsSessionRecord) -> None:
        """Create or update the session for the given user/session."""
        key = (record.user_id, record.session_id)
        self._sessions[key] = record

    def get_session(self, user_id: str, session_id: str) -> AwsSessionRecord | None:
        """Retrieve the session for a given user/session, or None if missing/expired."""
        key = (user_id, session_id)
        record = self._sessions.get(key)
        if record is None:
            return None

        # Treat sessions as expired if past expiration or too close to expiry
        if record.is_expired(safety_margin_seconds=self.safety_margin_seconds):
            # Clean up expired record
            self._sessions.pop(key, None)
            return None

        return record

    def delete_session(self, user_id: str, session_id: str) -> None:
        """Delete the session for the given user/session, if it exists."""
        key = (user_id, session_id)
        self._sessions.pop(key, None)
