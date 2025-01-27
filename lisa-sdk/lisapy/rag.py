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
from typing import BinaryIO, Dict, List, Mapping

from .common import BaseMixin
from .errors import parse_error


class RagMixin(BaseMixin):
    """Mixin for rag-related operations."""

    def list_documents(self, repo_id: str, collection_id: str) -> List[Dict]:
        """Add collection_id as query parameter to request"""
        url = f"{self.url}/repository/{repo_id}/document"
        params = {
            "collectionId": collection_id,
        }
        response = self._session.get(url, params=params)
        if response.status_code == 200:
            docs: List[Dict] = response.json()
            return docs
        else:
            raise parse_error(response.status_code, response)

    def delete_document_by_ids(self, repo_id: str, collection_id: str, doc_ids: list[str]) -> dict:
        url = f"{self.url}/repository/{repo_id}/document"
        params = {
            "collectionId": collection_id,
        }
        body = {
            "documentIds": doc_ids,
        }
        response = self._session.delete(url=url, params=params, data=body)
        if response.status_code == 200:
            deleted_docs: dict = response.json()
            return deleted_docs
        else:
            raise parse_error(response.status_code, response)

    def delete_documents_by_name(self, repo_id: str, collection_id: str, doc_name: str) -> dict:
        url = f"{self.url}/repository/{repo_id}/document"
        params = {
            "collectionId": collection_id,
            "documentName": doc_name,
        }
        response = self._session.delete(url=url, params=params)
        if response.status_code == 200:
            deleted_docs: dict = response.json()
            return deleted_docs
        else:
            raise parse_error(response.status_code, response)

    def _presigned_url(self, file_name: str) -> dict:
        url = f"{self.url}/repository/presigned-url"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = self._session.post(url, headers=headers, data=file_name)

        if response.status_code == 200:
            json_resp: dict = response.json().get("response")
            return json_resp
        else:
            raise parse_error(response.status_code, response)

    def _upload_document(self, presigned_url: str, filename: str) -> bool:
        with open(filename, "rb") as f:
            files: Mapping[str, tuple[str | None, BinaryIO | str, str]] = {
                "key": (None, filename, "text/plain"),
                "file": (filename, f, "application/octet-stream"),
            }
            response = self._session.post(presigned_url, files=files)

        if response.status_code == 204 or response.status_code == 200:
            logging.info("File uploaded successfully")
            return True
        else:
            logging.info(f"Error uploading file: {response.status_code}")
            logging.info(response.text)
            raise parse_error(response.status_code, response)

    def ingest_document(
        self, repo_id: str, model_id: str, file: str, chuck_size: int = 512, chuck_overlap: int = 51
    ) -> None:
        url = f"{self.url}/repository/{repo_id}/bulk"
        params: Dict[str, str | int] = {
            "repositoryType": repo_id,
            "chunkSize": chuck_size,
            "chunkOverlap": chuck_overlap,
        }
        payload = {"embeddingModel": {"modelName": model_id}, "keys": [file]}
        response = self._session.post(url, params=params, json=payload)
        if response.status_code == 200:
            logging.info("Request successful")
            logging.info(response.json())
        else:
            raise parse_error(response.status_code, response)

    def similarity_search(self, repo_id: str, model_name: str, query: str, k: int = 3) -> List[Dict]:
        url = f"{self.url}/repository/{repo_id}/similaritySearch"
        params: dict[str, str | int] = {"query": query, "modelName": model_name, "repositoryType": repo_id, "topK": k}

        response = self._session.get(url, params=params)
        if response.status_code == 200:
            results = response.json()
            docs: List[Dict] = results.get("docs", [])
            for doc in docs:
                logging.info("Document content:", doc["Document"]["page_content"])
                logging.info("Metadata:", doc["Document"]["metadata"])
                logging.info("---")

            return docs
        else:
            logging.info(f"Error: {response.status_code}")
            logging.info(response.text)
            raise parse_error(response.status_code, response)
