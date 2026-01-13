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
import os

import requests  # type: ignore[import-untyped,unused-ignore]

from .common import BaseMixin
from .errors import parse_error


class RagMixin(BaseMixin):
    """Mixin for rag-related operations."""

    def list_documents(self, repo_id: str, collection_id: str) -> list[dict]:
        """List documents in a collection.

        Args:
            repo_id: Repository ID
            collection_id: Collection ID

        Returns:
            List of document dictionaries
        """
        url = f"{self.url}/repository/{repo_id}/document"
        params = {
            "collectionId": collection_id,
        }
        response = self._session.get(url, params=params)
        if response.status_code == 200:
            result = response.json()
            # API returns {"documents": [...], "lastEvaluated": ..., ...}
            return result.get("documents", [])  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def get_document(self, repo_id: str, document_id: str) -> dict:
        """Get a single document by ID.

        Args:
            repo_id: Repository ID
            document_id: Document ID

        Returns:
            Document dictionary
        """
        url = f"{self.url}/repository/{repo_id}/{document_id}"
        response = self._session.get(url)
        if response.status_code == 200:
            return response.json()  # type: ignore[no-any-return]
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
        response = self._session.delete(url=url, params=params, json=body)
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
            # Extract key from fields for convenience
            if "fields" in json_resp and "key" in json_resp["fields"]:
                json_resp["key"] = json_resp["fields"]["key"]
            logging.debug(f"Presigned URL response: {json_resp}")
            return json_resp
        else:
            raise parse_error(response.status_code, response)

    def _upload_document(self, presigned_data: dict, filename: str) -> bool:
        """Upload document using presigned POST data.

        Args:
            presigned_data: Dictionary containing 'url' and 'fields' from presigned POST
            filename: Path to file to upload

        Returns:
            True if upload successful
        """
        url: str | None = presigned_data.get("url")
        if not url:
            raise ValueError("Presigned data missing 'url' field")

        fields = presigned_data.get("fields", {})

        with open(filename, "rb") as f:
            # Use basename for the filename in the upload
            basename = os.path.basename(filename)
            files = {"file": (basename, f)}
            # Use a new session without auth headers for S3 upload
            response = requests.post(url, data=fields, files=files, timeout=300)  # nosec B113

        if response.status_code == 204 or response.status_code == 200:
            logging.info("File uploaded successfully")
            return True
        else:
            logging.error(f"S3 upload failed with status {response.status_code}")
            logging.error(f"Response headers: {dict(response.headers)}")
            logging.error(f"Response body: {response.text[:500]}")
            # Try to parse XML error from S3
            try:
                from defusedxml import ElementTree as ET  # noqa: PLC0415 nosec B405

                root = ET.fromstring(response.text)  # nosec B314
                error_code = root.find(".//Code")
                error_msg = root.find(".//Message")
                if error_code is not None and error_msg is not None:
                    logging.error(f"S3 Error: {error_code.text} - {error_msg.text}")
            except Exception as xml_error:
                logging.debug(f"Could not parse S3 XML error response: {xml_error}")
            raise parse_error(response.status_code, response)

    def ingest_document(
        self,
        repo_id: str,
        model_id: str,
        file: str,
        chuck_size: int = 512,
        chuck_overlap: int = 51,
        collection_id: str | None = None,
    ) -> list[dict]:
        """Ingest a document and return job information.

        Returns:
            List of job dictionaries with jobId, documentId, status, s3Path
        """
        url = f"{self.url}/repository/{repo_id}/bulk"
        params: dict[str, str | int] = {
            "repositoryType": repo_id,
            "chunkSize": chuck_size,
            "chunkOverlap": chuck_overlap,
        }

        payload: dict[str, str | dict | list] = {"embeddingModel": {"modelName": model_id}, "keys": [file]}
        # Add collectionId to body, not query params
        if collection_id:
            payload["collectionId"] = collection_id

        response = self._session.post(url, params=params, json=payload)
        if response.status_code == 200:
            result = response.json()
            logging.info("Request successful")
            logging.info(f"Full response: {result}")
            jobs = result.get("jobs", [])
            logging.info(f"Jobs extracted: {jobs}")
            return jobs  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def similarity_search(
        self, repo_id: str, query: str, k: int = 3, collection_id: str | None = None, model_name: str | None = None
    ) -> list[dict]:
        """Perform similarity search.

        Args:
            repo_id: Repository ID
            query: Search query
            k: Number of results
            collection_id: Optional collection id (will use collection's embedding model)
            model_name: Optional model name (required if collection_id not provided)
        """
        url = f"{self.url}/repository/{repo_id}/similaritySearch"
        params: dict[str, str | int] = {"query": query, "repositoryType": repo_id, "topK": k}

        if collection_id:
            params["collectionId"] = collection_id

        if model_name:
            params["modelName"] = model_name

        response = self._session.get(url, params=params)
        if response.status_code == 200:
            results = response.json()
            docs: list[dict] = results.get("docs", [])
            for doc in docs:
                logging.info("Document content:", doc["Document"]["page_content"])
                logging.info("Metadata:", doc["Document"]["metadata"])
                logging.info("---")

            return docs
        else:
            logging.info(f"Error: {response.status_code}")
            logging.info(response.text)
            raise parse_error(response.status_code, response)
