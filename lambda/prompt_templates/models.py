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

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from utilities.time import iso_string


class PromptTemplateType(StrEnum):
    """Enum representing the prompt template type."""

    PERSONA = "persona"
    DIRECTIVE = "directive"


class PromptTemplateModel(BaseModel):
    """
    A Pydantic model representing a template for prompts.
    Contains metadata and functionality to create new revisions.
    """

    # Unique identifier for the prompt template
    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp of when the prompt template was created
    created: str | None = Field(default_factory=iso_string)

    # Owner of the prompt template
    owner: str

    # List of groups that have access to the prompt template
    groups: list[str] = Field(default=[])

    # Title of the prompt template
    title: str

    # Current revision number of the prompt template
    revision: int | None = Field(default=1)

    # Flag indicating if this is the latest revision
    latest: bool | None = Field(default=True)

    type: PromptTemplateType = Field(default=PromptTemplateType.PERSONA)

    # The main body content of the prompt template
    body: str

    def new_revision(self, update: dict[str, Any]) -> "PromptTemplateModel":
        """
        Create a new revision of the current prompt template.

        Args:
            update (Dict[str, Any]): A dictionary containing fields to update in the new revision.

        Returns:
            PromptTemplateModel: A new instance of PromptTemplateModel with updated attributes.
        """
        result: PromptTemplateModel = self.model_copy(
            update=update | {"created": iso_string(), "revision": (self.revision or 0) + 1}
        )
        return result
