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

"""Lambda functions for managing sessions."""
import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

import boto3
import create_env_variables  # noqa: F401
from botocore.exceptions import ClientError
from utilities.common_functions import api_wrapper, get_session_id, get_username, retry_config

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["SESSIONS_TABLE_NAME"])


def _get_all_user_sessions(user_id: str) -> List[Dict[str, Any]]:
    """Get all sessions for a user from DynamoDB.

    Parameters
    ----------
    user_id : str
        The user id.

    Returns
    -------
    List[Dict[str, Any]]
        A list of user sessions.
    """
    response = {}
    try:
        response = table.query(
            KeyConditionExpression="userId = :user_id",
            ExpressionAttributeValues={":user_id": user_id},
            IndexName=os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"],
            ScanIndexForward=False
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No sessions found for user {user_id}")
        else:
            logger.exception("Error listing sessions")
    return response.get("Items", [])  # type: ignore [no-any-return]


def _delete_user_session(session_id: str, user_id: str) -> Dict[str, bool]:
    """Delete a session from DynamoDB.

    Parameters
    ----------
    session_id : str
        The session id.
    user_id : str
        The user id.

    Returns
    -------
    Dict[str, bool]
        A dictionary containing the deleted status.
    """
    deleted = False
    try:
        table.delete_item(Key={"sessionId": session_id, "userId": user_id})
        deleted = True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {session_id}")
        else:
            logger.exception("Error deleting session")
    return {"deleted": deleted}


@api_wrapper
def list_sessions(event: dict, context: dict) -> List[Dict[str, Any]]:
    """List sessions by user ID from DynamoDB."""
    user_id = get_username(event)

    logger.info(f"Listing sessions for user {user_id}")
    return _get_all_user_sessions(user_id)


@api_wrapper
def get_session(event: dict, context: dict) -> Dict[str, Any]:
    """Get session from DynamoDB."""
    user_id = get_username(event)
    session_id = get_session_id(event)

    logger.info(f"Fetching session with ID {session_id} for user {user_id}")
    response = {}
    try:
        response = table.get_item(Key={"sessionId": session_id, "userId": user_id})
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {session_id}")
        else:
            logger.exception("Error fetching session")
    return response.get("Item", {})  # type: ignore [no-any-return]


@api_wrapper
def delete_session(event: dict, context: dict) -> dict:
    """Delete session from DynamoDB."""
    user_id = get_username(event)
    session_id = get_session_id(event)

    logger.info(f"Deleting session with ID {session_id} for user {user_id}")
    return _delete_user_session(session_id, user_id)


@api_wrapper
def delete_user_sessions(event: dict, context: dict) -> Dict[str, bool]:
    """Delete sessions by user ID from DyanmoDB."""
    user_id = get_username(event)

    logger.info(f"Deleting all sessions for user {user_id}")
    sessions = _get_all_user_sessions(user_id)
    logger.debug(f"Found user sessions: {sessions}")
    for session in sessions:
        _delete_user_session(session["sessionId"], user_id)
    return {"deleted": True}


# TODO: add validation for messages
@api_wrapper
def put_session(event: dict, context: dict) -> None:
    """Append the message to the record in DynamoDB."""
    user_id = get_username(event)
    session_id = get_session_id(event)
    # from https://stackoverflow.com/a/71446846
    body = json.loads(event["body"], parse_float=Decimal)
    messages = body["messages"]

    try:
        table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression="SET #history = :history, #startTime = :startTime, " +
                            "#createTime = if_not_exists(#createTime, :createTime)",
            ExpressionAttributeNames={
                "#history": "history",
                "#startTime": "startTime",
                "#createTime": "createTime"
            },
            ExpressionAttributeValues={
                ":history": messages,
                ":startTime": datetime.now().isoformat(),
                ":createTime": datetime.now().isoformat(),
            },
            ReturnValues="UPDATED_NEW"
        )
    except ClientError:
        logger.exception("Error updating session in DynamoDB")
