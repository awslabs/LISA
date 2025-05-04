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

import boto3
from models.domain_objects import Enum, IngestionJob

logger = logging.getLogger(__name__)


class IngestionAction(str, Enum):
    Ingest = "ingest"
    Delete = "delete"


class DocumentIngestionService:
    def _submit_job(self, job: IngestionJob, action: IngestionAction) -> None:
        # Submit AWS Batch job
        batch_client = boto3.client("batch")
        response = batch_client.submit_job(
            jobName=f"document-{action.value}-{job.id}",
            jobQueue=os.environ["LISA_INGESTION_JOB_QUEUE_NAME"],
            jobDefinition=os.environ["LISA_INGESTION_JOB_DEFINITION_NAME"],
            parameters={"DOCUMENT_ID": job.id, "ACTION": action},
        )
        logger.info(f"Submitted {action} job for document {job.id}: {response['jobId']}")

    def create_ingest_job(self, job: IngestionJob) -> None:
        self._submit_job(job, IngestionAction("ingest"))

    def create_delete_job(self, job: IngestionJob) -> None:
        self._submit_job(job, IngestionAction("delete"))
