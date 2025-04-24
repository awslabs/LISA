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
import base64
import json
import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

import boto3
import create_env_variables  # noqa: F401
from botocore.exceptions import ClientError
from utilities.common_functions import api_wrapper, get_session_id, get_username, retry_config

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_resource = boto3.resource("s3", region_name=os.environ["AWS_REGION"])
table = dynamodb.Table(os.environ["SESSIONS_TABLE_NAME"])
s3_bucket_name = os.environ["GENERATED_IMAGES_S3_BUCKET_NAME"]


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
            ScanIndexForward=False,
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
        bucket = s3_resource.Bucket(s3_bucket_name)
        bucket.objects.filter(Prefix=f"images/{session_id}").delete()
        deleted = True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {session_id}")
        else:
            logger.exception("Error deleting session")
    return {"deleted": deleted}


def _generate_presigned_image_url(key: str) -> str:
    url: str = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": s3_bucket_name,
            "Key": key,
            "ResponseContentType": "image/png",
            "ResponseCacheControl": "no-cache",
            "ResponseContentDisposition": "inline",
        },
        ExpiresIn=3600,
    )
    return url


@api_wrapper
def list_sessions(event: dict, context: dict) -> List[Dict[str, Any]]:
    """List sessions by user ID from DynamoDB."""
    user_id = get_username(event)

    logger.info(f"Listing sessions for user {user_id}")
    sessions = _get_all_user_sessions(user_id)
    resp = []
    for session in sessions:
        resp.append(
            {
                "sessionId": session["sessionId"],
                "firstHumanMessage": next(
                    (msg["content"] for msg in session.get("history", []) if msg.get("type") == "human"), ""
                ),
                "startTime": session.get("startTime", None),
                "createTime": session.get("createTime", None),
            }
        )
    return resp


@api_wrapper
def get_session(event: dict, context: dict) -> dict:
    """Get a session from DynamoDB."""
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        logging.info(f"Fetching session with ID {session_id} for user {user_id}")

        response = table.get_item(Key={"sessionId": session_id, "userId": user_id})
        resp = response.get("Item", {})

        for message in resp.get("history", []):
            if isinstance(message.get("content", None), List):
                for item in message.get("content", None):
                    if item.get("type", None) == "image_url":
                        try:
                            image_url = _generate_presigned_image_url(item.get("image_url", {}).get("s3_key", None))
                            item["image_url"]["url"] = image_url
                        except Exception as e:
                            print(f"Error uploading to S3: {e}")

        return response.get("Item", {})  # type: ignore [no-any-return]
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


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


@api_wrapper
def attach_image_to_session(event: dict, context: dict) -> dict:
    """Append the message to the record in DynamoDB."""
    try:
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        if "message" not in body:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required fields: messages"})}

        message = body["message"]

        if (
            message.get("type", None) == "image_url"
            and message.get("image_url", {}).get("url", None) is not None
            and not message.get("image_url", {}).get("url", None).startswith("https://")
        ):
            try:
                image_content = message.get("image_url", {}).get("url", None)
                # Generate a unique key for the S3 object
                file_name = f"{uuid.uuid4()}.png"  # Gets the last part of the URL as filename
                s3_key = f"images/{session_id}/{file_name}"  # Organize files in an images/ prefix

                # Upload to S3
                s3_client.put_object(
                    Bucket=s3_bucket_name,
                    Key=s3_key,
                    Body=base64.b64decode(image_content.split(",")[1]),
                    ContentType="image/png",
                )
                message["image_url"]["url"] = _generate_presigned_image_url(s3_key)
                message["image_url"]["s3_key"] = s3_key
            except Exception as e:
                print(f"Error uploading to S3: {e}")

        return {"statusCode": 200, "body": message}
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper
def put_session(event: dict, context: dict) -> dict:
    """Append the message to the record in DynamoDB."""
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        if "messages" not in body:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required fields: messages"})}

        messages = body["messages"]

        table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression="SET #history = :history, #configuration = :configuration, #startTime = :startTime, "
            + "#createTime = if_not_exists(#createTime, :createTime)",
            ExpressionAttributeNames={
                "#history": "history",
                "#configuration": "configuration",
                "#startTime": "startTime",
                "#createTime": "createTime",
            },
            ExpressionAttributeValues={
                ":history": messages,
                ":configuration": body.get("configuration", None),
                ":startTime": datetime.now().isoformat(),
                ":createTime": datetime.now().isoformat(),
            },
            ReturnValues="UPDATED_NEW",
        )
        return {"statusCode": 200, "body": json.dumps({"message": "Session updated successfully"})}
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
