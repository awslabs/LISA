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

from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field
from requests import Session

from .model import ModelMixin
from .config import ConfigMixin
from .doc import DocsMixin
from .rag import RagMixin
from .session import SessionMixin
from .repository import RepositoryMixin

class LisaApi(BaseModel, RepositoryMixin, ModelMixin, ConfigMixin, DocsMixin, RagMixin, SessionMixin):
    url: str = Field(..., description="REST API url for LiteLLM")
    headers: Optional[Dict[str, str]] = Field(None, description="Headers for request.")
    cookies: Optional[Dict[str, str]] = Field(None, description="Cookies for request.")
    verify: Optional[Union[str, bool]] = Field(None, description="Whether to verify SSL certificates.")
    timeout: int = Field(10, description="Timeout in minutes request.")
    _session: Session

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._session = Session()
        if self.headers:
            self._session.headers = self.headers  # type: ignore
        if self.verify is not None:
            self._session.verify = self.verify
        if self.cookies:
            self._session.cookies = self.cookies  # type: ignore


# Create Models
# Manage Models

# Get API definition
# Get API Openapi docs

# RAG
# List repository
# Generate presigned url
# similarity_search
# ingest_documents
# List documents
# delete_document

# Session
# List History

# Chat
# generate chat
