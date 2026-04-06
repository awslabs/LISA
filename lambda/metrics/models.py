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

"""Pydantic models for metrics events."""

from typing import Any

from pydantic import BaseModel


class MetricsEvent(BaseModel):
    """Event model for usage metrics published to SQS.

    event_type : str
        "full"       — API token user or session-lambda event; owns all metrics.
        "token_only" — JWT/UI passthrough event; only carries token counts, session
                       lambda already counted the prompts. Do not write a sessionMetrics
                       entry — that would create synthetic sessions and pollute aggregation.
    """

    userId: str
    sessionId: str
    messages: list[dict[str, Any]]
    userGroups: list[str]
    timestamp: str
    eventType: str = "full"
    modelId: str | None = None
    promptTokens: int | None = None
    completionTokens: int | None = None
