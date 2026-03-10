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

"""Lambda functions for managing session projects."""
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import boto3
import create_env_variables  # noqa: F401
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from cachetools import cached, TTLCache  # type: ignore[import-untyped,unused-ignore]
from models.domain_objects import DeleteResponse, SuccessResponse
from pydantic import BaseModel, Field, field_validator
from session.repository import delete_user_session, get_all_user_sessions
from utilities.auth import get_username
from utilities.common_functions import api_wrapper
from utilities.time import iso_string

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
_s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"])
_s3_resource = boto3.resource("s3", region_name=os.environ["AWS_REGION"])
_s3_bucket_name = os.environ.get("GENERATED_IMAGES_S3_BUCKET_NAME", "")
projects_table = dynamodb.Table(os.environ["PROJECTS_TABLE_NAME"])
sessions_table = dynamodb.Table(os.environ["SESSIONS_TABLE_NAME"])
config_table = dynamodb.Table(os.environ["CONFIG_TABLE_NAME"])

executor = ThreadPoolExecutor(max_workers=10)

# Module-level TTLCache — same pattern as lambda/session/lambda_functions.py, not a shared object
_config_cache: TTLCache = TTLCache(maxsize=1, ttl=300)


@cached(cache=_config_cache)
def _get_max_projects_per_user() -> int:
    """Read maxProjectsPerUser from the global config table (cached 5 min)."""
    try:
        response = config_table.query(
            KeyConditionExpression="configScope = :scope",
            ExpressionAttributeValues={":scope": "global"},
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        if items:
            return int(items[0].get("configuration", {}).get("maxProjectsPerUser", 10))
    except Exception as e:
        logger.error(f"Failed to read maxProjectsPerUser from config: {e}")
    return 50


# --- Pydantic request models ---


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class RenameProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DeleteProjectRequest(BaseModel):
    deleteSessions: bool = False

    @field_validator("deleteSessions", mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.lower() == "true"
        return bool(v)


class AssignSessionProjectRequest(BaseModel):
    unassign: bool = False

    @field_validator("unassign", mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.lower() == "true"
        return bool(v)


# --- Helpers ---


def _get_project_id(event: dict) -> str:
    project_id = event.get("pathParameters", {}).get("projectId")
    if not project_id:
        raise ValueError("projectId path parameter is required")
    return str(project_id)


def _get_session_id(event: dict) -> str:
    session_id = event.get("pathParameters", {}).get("sessionId")
    if not session_id:
        raise ValueError("sessionId path parameter is required")
    return str(session_id)


# --- Handlers ---


@api_wrapper
def list_projects(event: dict, context: dict) -> list[dict]:
    """List all projects for the calling user, sorted by createTime."""
    user_id = get_username(event)
    try:
        response = projects_table.query(
            KeyConditionExpression=Key("userId").eq(user_id),
        )
        items = [i for i in response.get("Items", []) if i.get("status") != "deleting"]
        items.sort(key=lambda x: x.get("createTime", ""))
        return items
    except ClientError as e:
        logger.exception("Error listing projects")
        raise e


@api_wrapper
def create_project(event: dict, context: dict) -> dict:
    """Create a new project; enforces maxProjectsPerUser limit."""
    user_id = get_username(event)

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as e:
        return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {e}"})}

    try:
        request = CreateProjectRequest.model_validate(body)
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    max_projects = _get_max_projects_per_user()

    # Count existing projects for this user
    try:
        count_response = projects_table.query(
            KeyConditionExpression=Key("userId").eq(user_id),
            Select="COUNT",
        )
        current_count = count_response.get("Count", 0)
    except ClientError as e:
        logger.exception("Error counting projects")
        raise e

    if current_count >= max_projects:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Project limit of {max_projects} reached"}),
        }

    now = iso_string()
    project_id = str(uuid.uuid4())
    item = {
        "userId": user_id,
        "projectId": project_id,
        "name": request.name,
        "createTime": now,
        "lastUpdated": now,
    }
    projects_table.put_item(Item=item)
    return item


@api_wrapper
def rename_project(event: dict, context: dict) -> SuccessResponse | dict:
    """Rename a project; validates ownership."""
    user_id = get_username(event)
    try:
        project_id = _get_project_id(event)
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as e:
        return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {e}"})}

    try:
        request = RenameProjectRequest.model_validate(body)
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    try:
        projects_table.update_item(
            Key={"userId": user_id, "projectId": project_id},
            UpdateExpression="SET #name = :name, #lastUpdated = :lastUpdated",
            ConditionExpression="attribute_exists(projectId)",
            ExpressionAttributeNames={"#name": "name", "#lastUpdated": "lastUpdated"},
            ExpressionAttributeValues={":name": request.name, ":lastUpdated": iso_string()},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"statusCode": 404, "body": json.dumps({"error": "Project not found"})}
        raise e

    return SuccessResponse(message="Project renamed successfully")


@api_wrapper
def delete_project(event: dict, context: dict) -> DeleteResponse | dict:
    """Delete a project; optionally cascade-delete its sessions."""
    user_id = get_username(event)
    try:
        project_id = _get_project_id(event)
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        body = {}

    request = DeleteProjectRequest.model_validate(body)

    # Phase 1: soft-delete — mark project as deleting to block new assignments
    try:
        projects_table.update_item(
            Key={"userId": user_id, "projectId": project_id},
            UpdateExpression="SET #status = :deleting",
            ConditionExpression="attribute_exists(projectId)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":deleting": "deleting"},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"statusCode": 404, "body": json.dumps({"error": "Project not found"})}
        raise e

    # Phase 2: find sessions belonging to this project via byUserId GSI + Python filter
    all_sessions = get_all_user_sessions(sessions_table, user_id)
    project_sessions = [s for s in all_sessions if s.get("projectId") == project_id]

    if request.deleteSessions:
        list(
            executor.map(
                lambda s: delete_user_session(
                    sessions_table, _s3_resource, _s3_client, _s3_bucket_name, s["sessionId"], user_id
                ),
                project_sessions,
            )
        )
    else:
        # Clear projectId from sessions so they return to History
        def _clear_project_id(session: dict) -> None:
            try:
                sessions_table.update_item(
                    Key={"sessionId": session["sessionId"], "userId": user_id},
                    UpdateExpression="REMOVE projectId",
                )
            except ClientError as e:
                logger.warning(f"Failed to clear projectId on session {session['sessionId']}: {e}")

        list(executor.map(_clear_project_id, project_sessions))

    # Phase 3: hard-delete the project item
    projects_table.delete_item(Key={"userId": user_id, "projectId": project_id})
    return DeleteResponse(deleted=True)


@api_wrapper
def assign_session_project(event: dict, context: dict) -> SuccessResponse | dict:
    """Assign or unassign a session to/from a project."""
    user_id = get_username(event)
    try:
        project_id = _get_project_id(event)
        session_id = _get_session_id(event)
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        body = {}

    request = AssignSessionProjectRequest.model_validate(body)

    # Ownership check 1: session must belong to calling user
    session_resp = sessions_table.get_item(Key={"sessionId": session_id, "userId": user_id})
    if not session_resp.get("Item"):
        return {"statusCode": 404, "body": json.dumps({"error": "Session not found"})}

    # Ownership check 2: project must belong to calling user (skip for unassign)
    if not request.unassign:
        project_resp = projects_table.get_item(Key={"userId": user_id, "projectId": project_id})
        if not project_resp.get("Item"):
            return {"statusCode": 404, "body": json.dumps({"error": "Project not found"})}
        # Reject assignment to a project that is being deleted
        if project_resp["Item"].get("status") == "deleting":
            return {"statusCode": 409, "body": json.dumps({"error": "Project is being deleted"})}

    now = iso_string()
    if request.unassign:
        sessions_table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression="REMOVE projectId",
        )
        try:
            projects_table.update_item(
                Key={"userId": user_id, "projectId": project_id},
                UpdateExpression="SET lastUpdated = :ts",
                ConditionExpression="attribute_exists(projectId)",
                ExpressionAttributeValues={":ts": now},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return {"statusCode": 404, "body": json.dumps({"error": "Project not found"})}
            raise e
    else:
        sessions_table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression="SET projectId = :pid",
            ExpressionAttributeValues={":pid": project_id},
        )
        projects_table.update_item(
            Key={"userId": user_id, "projectId": project_id},
            UpdateExpression="SET lastUpdated = :ts",
            ExpressionAttributeValues={":ts": now},
        )

    return SuccessResponse(message="Session assignment updated successfully")
