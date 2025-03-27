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
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PromptTemplateModel(BaseModel):
    """
    A Pydantic model representing a template for prompts.
    Contains metadata and functionality to create new revisions.
    """

    # Unique identifier for the prompt template
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp of when the prompt template was created
    created: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())

    # Owner of the prompt template
    owner: str

    # List of groups that have access to the prompt template
    groups: List[str] = Field(default=[])

    # Title of the prompt template
    title: str

    # Current revision number of the prompt template
    revision: Optional[int] = Field(default=1)

    # Flag indicating if this is the latest revision
    latest: Optional[bool] = Field(default=True)

    # The main body content of the prompt template
    body: str

    def new_revision(self, update: Dict[str, Any]) -> "PromptTemplateModel":
        """
        Create a new revision of the current prompt template.

        Args:
            update (Dict[str, Any]): A dictionary containing fields to update in the new revision.

        Returns:
            PromptTemplateModel: A new instance of PromptTemplateModel with updated attributes.
        """
        return self.model_copy(  # type: ignore
            update=update | {"created": datetime.now().isoformat(), "revision": (self.revision or 0) + 1}
        )
