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

"""AWS session management package for MCP Workbench.

This package contains helper types and utilities for managing short-lived AWS session credentials on a per-(user,
session) basis.
"""

from .identity import CallerIdentity as CallerIdentity
from .identity import CallerIdentityError as CallerIdentityError
from .identity import get_caller_identity as get_caller_identity
from .session_service import AwsSessionService
from .session_store import InMemoryAwsSessionStore
from .sts_client import AwsStsClient

# Shared singletons — both the HTTP routes and MCP tools must use the same
# instances so credentials connected via /api/aws/connect are visible to tools.
shared_session_store = InMemoryAwsSessionStore(safety_margin_seconds=60)
shared_session_service = AwsSessionService(store=shared_session_store)
shared_sts_client = AwsStsClient()
