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
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    created: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())
    owner: str
    groups: List[str] = Field(default=[])
    title: str
    revision: Optional[int] = Field(default=1)
    latest: Optional[bool] = Field(default=True)
    body: str

    def new_revision(self, update: Dict[str, Any]) -> "PromptTemplateModel":
        return self.model_copy(
            update=update | {"created": datetime.now().isoformat(), "revision": (self.revision or 0) + 1}
        )
