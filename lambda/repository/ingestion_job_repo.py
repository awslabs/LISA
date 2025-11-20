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

"""Repository for ingestion job DynamoDB operations."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import boto3
from models.domain_objects import IngestionJob, IngestionStatus
from utilities.common_functions import retry_config

logger = logging.getLogger(__name__)


def _get_ingestion_job_table():
    """Lazy initialization of DynamoDB table."""
    dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
    return dynamodb.Table(os.environ["LISA_INGESTION_JOB_TABLE_NAME"])


class IngestionJobListResponse:
    def __init__(self, jobs: list[IngestionJob], continuation_token: Optional[str]):
        self.jobs = jobs
        self.continuation_token = continuation_token


class RepositoryError(Exception):
    """Exception raised for errors that occur during repository operations.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class IngestionJobRepository:
    def __init__(self):
        self._ddb_client = None
        self._table_name = None
        self._batch_client = None

    @property
    def ddb_client(self):
        if self._ddb_client is None:
            self._ddb_client = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        return self._ddb_client

    @property
    def table_name(self):
        if self._table_name is None:
            self._table_name = os.environ["LISA_INGESTION_JOB_TABLE_NAME"]
        return self._table_name

    @property
    def batch_client(self):
        if self._batch_client is None:
            self._batch_client = boto3.client("batch", region_name=os.environ["AWS_REGION"], config=retry_config)
        return self._batch_client

    def save(self, job: IngestionJob) -> None:
        _get_ingestion_job_table().put_item(Item=job.model_dump(exclude_none=True))

    def find_by_id(self, id: str) -> IngestionJob:
        response = _get_ingestion_job_table().get_item(Key={"id": id})

        if not response.get("Item"):
            raise Exception(f"Ingestion job with id {id} not found")

        return IngestionJob(**response.get("Item"))

    def find_by_path(self, s3_path: str) -> list[IngestionJob]:
        response = _get_ingestion_job_table().query(
            IndexName="s3Path", KeyConditionExpression="s3Path = :path", ExpressionAttributeValues={":path": s3_path}
        )

        items = response.get("Items", [])
        return [IngestionJob(**item) for item in items]

    def find_by_document(self, document_id: str) -> Optional[IngestionJob]:
        response = _get_ingestion_job_table().query(
            IndexName="documentId",
            KeyConditionExpression="document_id = :document_id",
            ExpressionAttributeValues={":document_id": document_id},
        )

        items = response.get("Items", [])
        if not items:
            return None

        # there can only be one IngestionJob per RagDocument.id
        return IngestionJob(**items[0])

    def update_status(self, job: IngestionJob, status: IngestionStatus) -> IngestionJob:
        job.status = status
        _get_ingestion_job_table().update_item(
            Key={
                "id": job.id,
            },
            UpdateExpression="SET #field = :value",
            ExpressionAttributeNames={"#field": "status"},
            ExpressionAttributeValues={":value": status},
            ReturnValues="UPDATED_NEW",
        )

        return job

    def list_jobs_by_repository(
        self,
        repository_id: str,
        username: str,
        is_admin: bool,
        time_limit_hours: int = 1,
        page_size: int = 10,
        last_evaluated_key: Optional[Dict[str, str]] = None,
    ) -> tuple[list[IngestionJob], Optional[Dict[str, str]]]:
        """List ingestion jobs filtered by repository, user permissions, and time limit with pagination.

        Args:
            repository_id: The repository ID to filter by
            username: The username for non-admin filtering
            is_admin: Whether the user is an admin
            time_limit_hours: Time limit in hours (default: 1)
            page_size: Number of jobs to return per page (default: 10)
            last_evaluated_key: Pagination token from previous request

        Returns:
            Tuple of (list of job dictionaries, last_evaluated_key for next page)
        """
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=time_limit_hours)
        time_threshold_str = time_threshold.isoformat()

        # Use Query operation with GSI for better performance
        # GSI should have: PK=repository_id, SK=created_date
        gsi_name = "repository_id-created_date-index"  # Adjust this to match your actual GSI name

        try:
            # Build query parameters for efficient GSI query
            query_params = {
                "IndexName": gsi_name,
                "KeyConditionExpression": "repository_id = :repository_id AND created_date >= :time_threshold",
                "ExpressionAttributeValues": {":repository_id": repository_id, ":time_threshold": time_threshold_str},
                "ScanIndexForward": False,  # Sort by created_date descending (newest first)
                "Limit": page_size,
            }

            # Add username filter for non-admin users
            if not is_admin:
                query_params["FilterExpression"] = "username = :username"
                query_params["ExpressionAttributeValues"].update({":username": username, ":system_username": "system"})

            # Add pagination token if provided
            if last_evaluated_key:
                query_params["ExclusiveStartKey"] = last_evaluated_key

            response = _get_ingestion_job_table().query(**query_params)

            logger.info(f"GSI query returned {len(response.get('Items', []))} items")

        except Exception as e:
            logger.error(f"Error querying GSI: {e}")
            raise RepositoryError("Error querying GSI for JobStatus")

        # Convert items to job objects
        jobs = []
        for item in response.get("Items", []):
            jobs.append(IngestionJob(**item))

        # Get the last evaluated key for pagination
        last_evaluated_key_response = response.get("LastEvaluatedKey")

        return jobs, last_evaluated_key_response

    def get_batch_job_status(self, job_id: str) -> Optional[str]:
        """Get the status of a batch job by job ID.

        Args:
            job_id: AWS Batch job ID

        Returns:
            Job status (SUBMITTED, PENDING, RUNNABLE, STARTING, RUNNING, SUCCEEDED, FAILED) or None
        """
        response = self.batch_client.describe_jobs(jobs=[job_id])
        if response.get("jobs"):
            return response["jobs"][0].get("status")
        return None

    def find_batch_job_for_document(self, document_id: str, job_queue: str) -> Optional[Dict]:
        """Find the batch job associated with a document ingestion.

        Args:
            document_id: Document ID
            job_queue: Batch job queue name

        Returns:
            Dict with jobId and status, or None if not found
        """
        job_name_prefix = f"document-ingest-{document_id}"

        for status in ["RUNNING", "SUCCEEDED", "FAILED", "PENDING", "RUNNABLE", "STARTING"]:
            try:
                response = self.batch_client.list_jobs(jobQueue=job_queue, jobStatus=status)
                for job in response.get("jobSummaryList", []):
                    if job["jobName"].startswith(job_name_prefix):
                        return {"jobId": job["jobId"], "status": status, "jobName": job["jobName"]}
            except Exception as e:  # nosec B112
                logger.debug(f"Error listing jobs with status {status}: {e}")

        return None

    def find_pending_collection_deletions(self, repository_id: str) -> list[IngestionJob]:
        """Find all pending collection deletion jobs for a repository.

        Args:
            repository_id: Repository ID

        Returns:
            List of pending collection deletion jobs
        """
        try:
            response = _get_ingestion_job_table().query(
                IndexName="repository_id-created_date-index",
                KeyConditionExpression="repository_id = :repo_id",
                FilterExpression=(
                    "attribute_exists(collection_deletion) AND collection_deletion = :true AND "
                    "(#status = :pending OR #status = :in_progress)"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":repo_id": repository_id,
                    ":true": True,
                    ":pending": IngestionStatus.DELETE_PENDING,
                    ":in_progress": IngestionStatus.DELETE_IN_PROGRESS,
                },
            )

            items = response.get("Items", [])
            return [IngestionJob(**item) for item in items]
        except Exception as e:
            logger.error(f"Error finding pending collection deletions for repository {repository_id}: {e}")
            return []
