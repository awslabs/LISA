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

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import boto3
from models.domain_objects import IngestionJob, IngestionStatus
from utilities.common_functions import retry_config

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
ingestion_job_table = dynamodb.Table(os.environ["LISA_INGESTION_JOB_TABLE_NAME"])


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
        self.ddb_client = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        self.table_name = os.environ["LISA_INGESTION_JOB_TABLE_NAME"]

    def save(self, job: IngestionJob) -> None:
        ingestion_job_table.put_item(Item=job.model_dump(exclude_none=True))

    def find_by_id(self, id: str) -> IngestionJob:
        response = ingestion_job_table.get_item(Key={"id": id})

        if not response.get("Item"):
            raise Exception(f"Ingestion job with id {id} not found")

        return IngestionJob(**response.get("Item"))

    def find_by_path(self, s3_path: str) -> list[IngestionJob]:
        response = ingestion_job_table.query(
            IndexName="s3Path", KeyConditionExpression="s3Path = :path", ExpressionAttributeValues={":path": s3_path}
        )

        items = response.get("Items", [])
        return [IngestionJob(**item) for item in items]

    def find_by_document(self, document_id: str) -> Optional[IngestionJob]:
        response = ingestion_job_table.query(
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
        ingestion_job_table.update_item(
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
        self, repository_id: str, username: str, is_admin: bool, time_limit_hours: int = 1
    ) -> Dict[str, Dict]:
        """List ingestion jobs filtered by repository, user permissions, and time limit.

        Args:
            repository_id: The repository ID to filter by
            username: The username for non-admin filtering
            is_admin: Whether the user is an admin
            time_limit_hours: Time limit in hours (default: 1)

        Returns:
            Dict mapping job IDs to job details
        """
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=time_limit_hours)
        time_threshold_str = time_threshold.isoformat()

        if is_admin:
            filter_expression = "repository_id = :repository_id AND created_date >= :time_threshold"
            expression_values = {":repository_id": {"S": repository_id}, ":time_threshold": {"S": time_threshold_str}}
        else:
            filter_expression = (
                "repository_id = :repository_id AND created_date >= :time_threshold AND username = :username"
            )
            expression_values = {
                ":repository_id": {"S": repository_id},
                ":time_threshold": {"S": time_threshold_str},
                ":username": {"S": username},
            }

        response = self.ddb_client.scan(
            TableName=self.table_name, FilterExpression=filter_expression, ExpressionAttributeValues=expression_values
        )

        job_details_map = {}
        for item in response.get("Items", []):
            job_id = item.get("id", {}).get("S", "")
            status = item.get("status", {}).get("S", "UNKNOWN")
            s3_path = item.get("s3_path", {}).get("S", "")
            job_username = item.get("username", {}).get("S", "")

            if job_id:
                document_name = s3_path.split("/")[-1] if s3_path else ""
                auto = job_username == "system"

                job_details_map[job_id] = {"status": status, "document": document_name, "auto": auto}

        return job_details_map
