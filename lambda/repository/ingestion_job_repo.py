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
from typing import Optional

import boto3
from models.domain_objects import IngestionJob, IngestionStatus
from models.lambda_functions import retry_config

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
ingestion_job_table = dynamodb.Table(os.environ["LISA_INGESTION_JOB_TABLE_NAME"])


class IngestionJobRepository:
    def save(self, job: IngestionJob) -> None:
        ingestion_job_table.put_item(Item=job.model_dump(exclude_none=True))

    def find_by_id(self, id: str) -> IngestionJob:
        response = ingestion_job_table.get_item(Key={"id": id})

        if not response.get("Item"):
            raise Exception(f"Ingestion job with id {id} not found")

        IngestionJob(**response.get("Item"))

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
