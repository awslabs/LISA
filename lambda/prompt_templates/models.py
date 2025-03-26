from datetime import datetime
from typing import List, Optional
import uuid
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

    def new_revision(self, update=dict[str, any]) -> "PromptTemplateModel":
        return self.model_copy(update=update | {
            'created': datetime.now().isoformat(),
            'revision': self.revision + 1
        })