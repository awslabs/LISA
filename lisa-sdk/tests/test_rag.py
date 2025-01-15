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
from typing import Any

import pytest
from lisapy import LisaApi


class TestLisaRag:

    @pytest.fixture(autouse=True)
    def setup_class(self, lisa_api: LisaApi) -> None:
        repos = lisa_api.list_repositories()
        models = lisa_api.list_embedding_models()
        self.repo_id: str = repos[0].get("repositoryId", "")
        self.collection_id: str = models[0].get("modelId", "")

    @pytest.mark.skip(reason="TODO: Implement test")
    def test_insert_doc(self, lisa_api: LisaApi) -> None:
        lisa_api.ingest_document(self.repo_id, self.collection_id, "test.txt")

    def test_list_docs(self, lisa_api: LisaApi) -> Any:
        documents = lisa_api.list_documents(self.repo_id, self.collection_id)
        logging.info(
            f"Found {len(documents)} documents in repo {self.repo_id} / collection {self.collection_id} - {documents}"
        )
        return documents

    @pytest.mark.skip(reason="TODO: Implement test")
    def test_delete_doc_by_id(self, lisa_api: LisaApi, test_list_docs: Any) -> None:
        logging.info(test_list_docs)
        # repo_id = "pgvector-rag"
        # collection_id = "intfloat-tei"
        # document_id = "3f738ec0-05e7-4707-989e-0f21d64ee81e"
        # try:
        #     response = lisa_api.delete_document_by_id(repo_id, collection_id, document_id)
        #     logging.info(f"{response}")
        # except Exception as e:
        #     assert "Document not found" in str(e)

    @pytest.mark.skip(reason="TODO: Implement test")
    def test_delete_docs_by_name(self, lisa_api: LisaApi, test_list_docs: Any) -> None:
        logging.info(test_list_docs)
        # repo_id = "pgvector-rag"
        # collection_id = "intfloat-tei"
        # document_name = "MLSpace.txt"
        # try:
        #     response = lisa_api.delete_documents_by_name(repo_id, collection_id, document_name)
        #     logging.info(f"{response}")
        # except Exception as e:
        #     assert "No documents found" in str(e)

    @pytest.mark.skip(reason="Management Token not supported")
    def test_similarity_search(self, lisa_api: LisaApi) -> None:
        response = lisa_api.similarity_search(self.repo_id, self.collection_id, "What is OversightML?")
        logging.info(f"{response}")
        assert len(response) > 0
        # repo_id = "pgvector-rag"
        # collection_id = "intfloat-tei"
        # query = "What is the name of the author of this document?"
        # response = lisa_api.similarity_search(repo_id, collection_id, query)
        # logging.info(f"{response}")
