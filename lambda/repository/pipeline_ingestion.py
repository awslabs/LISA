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

import os

from models.domain_objects import IngestionJob, IngestionStatus
from repository.ingestion_job_repo import IngestionJobRepository
from repository.pipeline_delete_document import pipeline_delete
from repository.pipeline_ingest_documents import pipeline_ingest, RagDocumentRepository

ingestion_job_repository = IngestionJobRepository()
doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])


def ingest(job: IngestionJob) -> None:
    ingestion_job_repository.update_status(job, IngestionStatus.IN_PROGRESS)
    pipeline_ingest(job)


def delete(job: IngestionJob) -> None:
    ingestion_job_repository.update_status(job, IngestionStatus.DELETING)
    pipeline_delete(job)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        job = ingestion_job_repository.find_by_id(sys.argv[2])

        if sys.argv[1] == "ingest" and len(sys.argv) > 2:
            ingest(job)
        elif sys.argv[1] == "delete" and len(sys.argv) > 2:
            delete(job)
