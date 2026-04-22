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

"""Pydantic models for workflow orchestration definitions."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field
from utilities.time import iso_string

WorkflowStepType = Literal["tool", "llm", "approval", "branch"]
WorkflowStatus = Literal["ACTIVE", "PAUSED"]


class WorkflowStep(BaseModel):
    stepId: str
    name: str
    type: WorkflowStepType
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    workflowId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    templateId: str | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)
    status: WorkflowStatus = "ACTIVE"
    allowedGroups: list[str] = Field(default_factory=list)
    created: str | None = Field(default_factory=iso_string)
    updated: str | None = Field(default_factory=iso_string)
