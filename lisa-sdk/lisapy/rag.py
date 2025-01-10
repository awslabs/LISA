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
import logging
from typing import Dict, List

from .common import BaseMixin
from .errors import parse_error


class RagMixin(BaseMixin):
    """Mixin for rag-related operations."""

    def list_documents(self, repo_id: str, collection_id: str) -> List[Dict]:
        """Add collection_id as query parameter to request"""
        logging.info(f"Using url: {self.url}/repository/{repo_id}/document?collectionId={collection_id}")
        response = self._session.get(f"{self.url}/repository/{repo_id}/document?collectionId={collection_id}")
        if response.status_code == 200:
            docs: List[Dict] = response.json()
            return docs
        else:
            raise parse_error(response.status_code, response)

    def delete_document_by_id(self, repo_id: str, collection_id: str, doc_id: str) -> dict:
        response = self._session.delete(
            f"{self.url}/repository/{repo_id}/document?collectionId={collection_id}&documentId={doc_id}"
        )
        if response.status_code == 200:
            deleted_docs: dict = response.json()
            return deleted_docs
        else:
            raise parse_error(response.status_code, response)

    def delete_documents_by_name(self, repo_id: str, collection_id: str, doc_name: str) -> dict:
        response = self._session.delete(
            f"{self.url}/repository/{repo_id}/document?collectionId={collection_id}&documentName={doc_name}"
        )
        if response.status_code == 200:
            deleted_docs: dict = response.json()
            return deleted_docs
        else:
            raise parse_error(response.status_code, response)


# TODO:
# - ingest_document
# - presigned_url
# - similarity_search
