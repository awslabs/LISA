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
from datetime import datetime, timedelta, timezone


@dataclass
class AwsSessionRecord:
    """In-memory representation of a short-lived AWS session for a user/session.

    The fields mirror the design in LISA_Auth.md, with expires_at stored as an aware UTC datetime.
    """

    user_id: str
    session_id: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_session_token: str
    aws_region: str
    expires_at: datetime

    def is_expired(self, *, safety_margin_seconds: int = 0) -> bool:
        """Return True if the record should be treated as expired."""
        now = datetime.now(timezone.utc)
        effective_expiry = self.expires_at
        if safety_margin_seconds > 0:
            effective_expiry = effective_expiry - timedelta(seconds=safety_margin_seconds)
        return now >= effective_expiry
