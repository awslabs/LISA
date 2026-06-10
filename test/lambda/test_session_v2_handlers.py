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

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials & env vars BEFORE importing session.lambda_functions.
# Use setdefault so we don't clobber values set by an earlier-imported test module
# (e.g. test_session_lambda.py runs first when collected together).
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SESSIONS_TABLE_NAME", "sessions-table")
os.environ.setdefault("MESSAGES_TABLE_NAME", "messages-table")
os.environ.setdefault("SESSIONS_BY_USER_ID_INDEX_NAME", "sessions-by-user-id-index")
os.environ.setdefault("GENERATED_IMAGES_S3_BUCKET_NAME", "bucket")
os.environ.setdefault("MODEL_TABLE_NAME", "model-table")
os.environ.setdefault("CONFIG_TABLE_NAME", "config-table")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "guardrails-table")
os.environ.setdefault("SESSION_ENCRYPTION_KEY_ARN", "arn:aws:kms:us-east-1:123456789012:key/test")


# sys.modules patch must run at import time so ``create_env_variables`` resolves.
# Stopping it would shadow the real module for tests collected later.
patch.dict("sys.modules", {"create_env_variables": MagicMock()}).start()

from session import lambda_functions  # noqa: E402
from session.lambda_functions import (  # noqa: E402
    _attach_presigned_urls,
    _find_first_human_message,
    compact_session,
    get_messages,
    get_session,
    post_messages,
    put_session,
)

# --- Fixtures ---


@pytest.fixture
def lambda_context():
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def aws():
    """Stand up moto + create all tables/buckets the handlers expect."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        sessions_table = ddb.create_table(
            TableName="sessions-table",
            KeySchema=[
                {"AttributeName": "sessionId", "KeyType": "HASH"},
                {"AttributeName": "userId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "sessionId", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "sessions-by-user-id-index",
                    "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        messages_table = ddb.create_table(
            TableName="messages-table",
            KeySchema=[
                {"AttributeName": "sessionId", "KeyType": "HASH"},
                {"AttributeName": "messageIndex", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "sessionId", "AttributeType": "S"},
                {"AttributeName": "messageIndex", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        config_table = ddb.create_table(
            TableName="config-table",
            KeySchema=[
                {"AttributeName": "configScope", "KeyType": "HASH"},
                {"AttributeName": "versionId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "configScope", "AttributeType": "S"},
                {"AttributeName": "versionId", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        s3_client = boto3.client("s3", region_name="us-east-1")
        # us-east-1 buckets are created without a LocationConstraint
        s3_client.create_bucket(Bucket="bucket")

        # Reset cached state on the lambda module for every test
        lambda_functions._encryption_cache.clear()

        # Patch the lambda module's boto3 globals to point at the moto-backed
        # resources. We also need to bind ``s3_client`` because some other
        # tests in the suite patch it to a MagicMock at module scope and the
        # leaked state breaks ``_attach_presigned_urls``.
        with patch.object(lambda_functions, "table", sessions_table), patch.object(
            lambda_functions, "messages_table", messages_table
        ), patch.object(lambda_functions, "config_table", config_table), patch.object(
            lambda_functions, "dynamodb", ddb
        ), patch.object(
            lambda_functions, "s3_client", s3_client
        ), patch.object(
            lambda_functions, "s3_resource", boto3.resource("s3", region_name="us-east-1")
        ):
            yield SimpleNamespace(
                sessions=sessions_table,
                messages=messages_table,
                config=config_table,
                s3=s3_client,
                ddb=ddb,
            )


def _claim_event(session_id="test-session", body=None, query=None, method=None):
    # api_wrapper validates `httpMethod`. Default to POST when a body is provided
    # (post_messages, compact_session, put_session) and GET otherwise (get_session,
    # get_messages). Callers can pass `method=` explicitly to override.
    if method is None:
        method = "POST" if body is not None else "GET"
    event = {
        # `get_username` reads `authorizer.username` directly (not the nested claims),
        # so we set both: the legacy `claims` for any helper that expects it, and the
        # top-level `username` so the actual handler sees `test-user`.
        "requestContext": {
            "authorizer": {
                "username": "test-user",
                "claims": {"username": "test-user"},
            }
        },
        "pathParameters": {"sessionId": session_id},
        "httpMethod": method,
        "path": f"/session/{session_id}",
    }
    if body is not None:
        event["body"] = body
    if query is not None:
        event["queryStringParameters"] = query
    return event


# --- _attach_presigned_urls ---


def test_attach_presigned_urls_replaces_image_keys(aws):
    """Patch the URL generator so the test is independent of the global
    s3_client state — other tests in the suite swap that client in/out and the
    leak makes a real-presign assertion non-deterministic."""
    msgs = [
        {
            "content": [
                {"type": "text", "text": "look"},
                {"type": "image_url", "image_url": {"s3_key": "images/test/foo.png", "url": "stale"}},
            ]
        }
    ]
    with patch("session.lambda_functions._generate_presigned_image_url", return_value="https://signed/image"):
        _attach_presigned_urls(msgs)
    assert msgs[0]["content"][1]["image_url"]["url"] == "https://signed/image"


def test_attach_presigned_urls_replaces_video_keys(aws):
    msgs = [
        {
            "content": [
                {"type": "video_url", "video_url": {"s3_key": "videos/test/foo.mp4", "url": "stale"}},
            ]
        }
    ]
    with patch("session.lambda_functions._generate_presigned_video_url", return_value="https://signed/video"):
        _attach_presigned_urls(msgs)
    assert msgs[0]["content"][0]["video_url"]["url"] == "https://signed/video"


def test_attach_presigned_urls_skips_string_content():
    msgs = [{"content": "just a string"}]
    _attach_presigned_urls(msgs)  # no error


def test_attach_presigned_urls_skips_blocks_without_s3_key():
    msgs = [
        {
            "content": [
                {"type": "image_url", "image_url": {"url": "https://external"}},
                {"type": "text", "text": "no s3"},
                {"type": "image_url", "image_url": {}},
            ]
        }
    ]
    _attach_presigned_urls(msgs)
    # Original (no s3_key) URL unchanged
    assert msgs[0]["content"][0]["image_url"]["url"] == "https://external"


def test_attach_presigned_urls_skips_non_dict_content_items():
    msgs = [{"content": ["bare string in list"]}]
    _attach_presigned_urls(msgs)


# --- post_messages ---


def test_post_messages_creates_v2_session_from_scratch(aws, lambda_context):
    body = json.dumps({"messages": [{"type": "human", "content": "hi"}], "name": "first"})
    resp = post_messages(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 200, resp["body"]

    # Sessions table updated with v2 metadata
    item = aws.sessions.get_item(Key={"sessionId": "test-session", "userId": "test-user"})["Item"]
    assert item["storageVersion"] == "2.0"
    assert int(item["messageCount"]) == 1
    # Message persisted in messages table
    msg = aws.messages.get_item(Key={"sessionId": "test-session", "messageIndex": 0})["Item"]
    assert msg["content"] == "hi"


def test_post_messages_returns_500_when_no_messages_table(aws, lambda_context):
    with patch.object(lambda_functions, "messages_table", None):
        resp = post_messages(
            _claim_event(body=json.dumps({"messages": [{"type": "human", "content": "x"}]})), lambda_context
        )
    assert resp["statusCode"] == 500
    assert "Messages table" in resp["body"]


def test_post_messages_invalid_json_400(aws, lambda_context):
    resp = post_messages(_claim_event(body="not-json"), lambda_context)
    assert resp["statusCode"] == 400


def test_post_messages_validation_error_400(aws, lambda_context):
    # `messages` is required
    resp = post_messages(_claim_event(body=json.dumps({})), lambda_context)
    assert resp["statusCode"] == 400


def test_post_messages_empty_messages_400(aws, lambda_context):
    resp = post_messages(_claim_event(body=json.dumps({"messages": []})), lambda_context)
    assert resp["statusCode"] == 400


def test_post_messages_increments_token_count_and_message_count(aws, lambda_context):
    body = json.dumps(
        {"messages": [{"type": "ai", "content": "hi", "usage": {"promptTokens": 3, "completionTokens": 5}}]}
    )
    resp = post_messages(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 200
    item = aws.sessions.get_item(Key={"sessionId": "test-session", "userId": "test-user"})["Item"]
    assert int(item["totalTokensUsed"]) == 8
    assert int(item["tokensUsedSinceCompaction"]) == 8
    assert int(item["messageCount"]) == 1


def test_post_messages_omitted_configuration_does_not_overwrite_existing(aws, lambda_context):
    """When the request omits `configuration`, the stored configuration on a v2 session
    must remain untouched. Otherwise an append-only follow-up would erase the user's
    selected model / RAG config."""
    existing_config = {
        "selectedModel": {"modelId": "kept-model", "modelName": "Kept", "streaming": True},
        "ragConfig": {"foo": "bar"},
    }
    aws.sessions.put_item(
        Item={
            "sessionId": "test-session",
            "userId": "test-user",
            "storageVersion": "2.0",
            "messageCount": 1,
            "configuration": existing_config,
        }
    )
    aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": 0, "type": "human", "content": "first"})

    body = json.dumps({"messages": [{"type": "ai", "content": "follow-up"}]})  # no `configuration` key
    resp = post_messages(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 200, resp["body"]

    item = aws.sessions.get_item(Key={"sessionId": "test-session", "userId": "test-user"})["Item"]
    # Configuration must be unchanged — the bug was that it would be replaced by an empty default.
    assert item["configuration"] == existing_config


def test_post_messages_lazy_migrates_legacy_session(aws, lambda_context):
    """A v1.0 session with `history` should migrate when post_messages first runs."""
    aws.sessions.put_item(
        Item={
            "sessionId": "test-session",
            "userId": "test-user",
            "history": [{"type": "human", "content": "old hi"}, {"type": "ai", "content": "old hello"}],
        }
    )
    resp = post_messages(
        _claim_event(body=json.dumps({"messages": [{"type": "human", "content": "new"}]})),
        lambda_context,
    )
    assert resp["statusCode"] == 200, resp["body"]
    # Migration moved the legacy 2 messages to the messages table; new message is appended
    msgs = aws.messages.scan().get("Items", [])
    contents = sorted(int(m["messageIndex"]) for m in msgs)
    assert contents == [0, 1, 2]
    item = aws.sessions.get_item(Key={"sessionId": "test-session", "userId": "test-user"})["Item"]
    assert "history" not in item


def test_post_messages_migration_failure_returns_500(aws, lambda_context):
    aws.sessions.put_item(
        Item={"sessionId": "test-session", "userId": "test-user", "history": [{"type": "human", "content": "x"}]}
    )
    with patch(
        "session.lambda_functions.migrate_session_to_v2",
        side_effect=ClientError(error_response={"Error": {"Code": "InternalServerError"}}, operation_name="UpdateItem"),
    ):
        resp = post_messages(
            _claim_event(body=json.dumps({"messages": [{"type": "human", "content": "n"}]})),
            lambda_context,
        )
    assert resp["statusCode"] == 500


def test_post_messages_write_failure_returns_500(aws, lambda_context):
    with patch("session.lambda_functions.put_message_with_index_retry", side_effect=RuntimeError("collision")):
        resp = post_messages(
            _claim_event(body=json.dumps({"messages": [{"type": "human", "content": "x"}]})),
            lambda_context,
        )
    assert resp["statusCode"] == 500


# --- get_messages ---


def test_get_messages_returns_paginated_messages(aws, lambda_context):
    aws.sessions.put_item(Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0"})
    for i in range(3):
        aws.messages.put_item(
            Item={"sessionId": "test-session", "messageIndex": i, "type": "human", "content": f"m{i}"}
        )

    resp = get_messages(_claim_event(query={"limit": "10", "order": "asc"}), lambda_context)
    assert resp["statusCode"] == 200, resp["body"]
    body = json.loads(resp["body"])
    assert len(body["messages"]) == 3
    assert body["hasMore"] is False


def test_get_messages_returns_404_when_session_missing(aws, lambda_context):
    resp = get_messages(_claim_event(), lambda_context)
    assert resp["statusCode"] == 404


def test_get_messages_returns_500_when_no_messages_table(aws, lambda_context):
    with patch.object(lambda_functions, "messages_table", None):
        resp = get_messages(_claim_event(), lambda_context)
    assert resp["statusCode"] == 500


def test_get_messages_caps_limit_at_200(aws, lambda_context):
    aws.sessions.put_item(Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0"})
    aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": 0, "type": "human", "content": "m"})
    # Request >200; helper should not crash
    resp = get_messages(_claim_event(query={"limit": "9999"}), lambda_context)
    assert resp["statusCode"] == 200


def test_get_messages_invalid_cursor_returns_400(aws, lambda_context):
    aws.sessions.put_item(Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0"})
    resp = get_messages(_claim_event(query={"cursor": "not-base64!!!"}), lambda_context)
    assert resp["statusCode"] == 400


@pytest.mark.parametrize("bad_limit", ["-1", "0", "foo", ""])
def test_get_messages_rejects_invalid_limit(aws, lambda_context, bad_limit):
    """Negative/zero limits must be clamped to 1 (handler succeeds), and non-numeric
    limits must return a 400 — DynamoDB would otherwise surface a
    ParamValidationError as a 500."""
    aws.sessions.put_item(Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0"})
    aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": 0, "type": "human", "content": "m"})
    resp = get_messages(_claim_event(query={"limit": bad_limit}), lambda_context)
    if bad_limit in ("-1", "0"):
        # Clamped up to 1 — handler should succeed. We treat negative/zero as "use
        # the smallest valid limit" rather than reject; they're benign, not malicious.
        assert resp["statusCode"] == 200, resp
    else:
        # The conftest's mock_api_wrapper passes through dicts with a statusCode key
        # unchanged, so we can assert on the top-level statusCode directly.
        assert resp["statusCode"] == 400, resp
        body = json.loads(resp["body"])
        assert "Invalid limit" in body.get("error", ""), body


def test_get_messages_emits_next_cursor_when_more_pages(aws, lambda_context):
    aws.sessions.put_item(Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0"})
    for i in range(5):
        aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": i, "content": f"m{i}"})
    resp = get_messages(_claim_event(query={"limit": "2", "order": "asc"}), lambda_context)
    body = json.loads(resp["body"])
    assert body["hasMore"] is True
    assert body["nextCursor"] is not None


# --- _find_first_human_message v2.0 path ---


def test_find_first_human_message_v2_returns_first_human(aws):
    aws.messages.put_item(Item={"sessionId": "s1", "messageIndex": 0, "type": "system", "content": "you are helpful"})
    aws.messages.put_item(Item={"sessionId": "s1", "messageIndex": 1, "type": "human", "content": "real question"})
    session = {"sessionId": "s1", "storageVersion": "2.0"}
    assert _find_first_human_message(session, user_id="u1") == "real question"


def test_find_first_human_message_v2_skips_context_prefix(aws):
    """Context-prefix human messages are filtered; the next non-prefix human is returned."""
    aws.messages.put_item(
        Item={
            "sessionId": "s1",
            "messageIndex": 0,
            "type": "human",
            "content": "File context: stuff",
        }
    )
    aws.messages.put_item(Item={"sessionId": "s1", "messageIndex": 1, "type": "human", "content": "actual q"})
    session = {"sessionId": "s1", "storageVersion": "2.0"}
    assert _find_first_human_message(session, user_id="u1") == "actual q"


def test_find_first_human_message_v2_handles_list_content(aws):
    aws.messages.put_item(
        Item={
            "sessionId": "s1",
            "messageIndex": 0,
            "type": "human",
            "content": [{"type": "text", "text": "block question"}],
        }
    )
    session = {"sessionId": "s1", "storageVersion": "2.0"}
    assert _find_first_human_message(session, user_id="u1") == "block question"


def test_find_first_human_message_v2_returns_empty_when_no_human(aws):
    aws.messages.put_item(Item={"sessionId": "s1", "messageIndex": 0, "type": "ai", "content": "only ai"})
    session = {"sessionId": "s1", "storageVersion": "2.0"}
    assert _find_first_human_message(session, user_id="u1") == ""


def test_find_first_human_message_v2_query_failure_returns_empty(aws):
    """If the messages-table query fails, the helper logs and returns empty string."""
    session = {"sessionId": "s1", "storageVersion": "2.0"}
    with patch.object(lambda_functions.messages_table, "query", side_effect=Exception("boom")):
        assert _find_first_human_message(session, user_id="u1") == ""


# --- get_session v2.0 branch ---


def test_get_session_v2_returns_messages_from_messages_table(aws, lambda_context):
    aws.sessions.put_item(
        Item={
            "sessionId": "test-session",
            "userId": "test-user",
            "storageVersion": "2.0",
            "configuration": {},
        }
    )
    for i in range(3):
        aws.messages.put_item(
            Item={"sessionId": "test-session", "messageIndex": i, "type": "human", "content": f"m{i}"}
        )

    resp = get_session(_claim_event(), lambda_context)
    assert resp["statusCode"] == 200, resp["body"]
    body = json.loads(resp["body"])
    # History returned in chronological order
    assert [m["content"] for m in body["history"]] == ["m0", "m1", "m2"]
    assert body["hasMoreMessages"] is False


def test_get_session_v2_emits_next_cursor_when_more_pages(aws, lambda_context):
    aws.sessions.put_item(
        Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0", "configuration": {}}
    )
    # Initial page is 20 messages — write more so paginated read returns LastEvaluatedKey
    for i in range(25):
        aws.messages.put_item(
            Item={"sessionId": "test-session", "messageIndex": i, "type": "human", "content": f"m{i}"}
        )

    resp = get_session(_claim_event(), lambda_context)
    body = json.loads(resp["body"])
    assert body["hasMoreMessages"] is True
    assert body["nextCursor"] is not None


def test_get_session_returns_404_when_missing(aws, lambda_context):
    resp = get_session(_claim_event(), lambda_context)
    assert resp["statusCode"] == 404


# --- put_session v2.0 branch (metadata-only update) ---


def test_put_session_v2_metadata_only_skips_history_write(aws, lambda_context):
    """v2 sessions: put_session must not touch history/totalTokensUsed."""
    aws.sessions.put_item(
        Item={
            "sessionId": "test-session",
            "userId": "test-user",
            "storageVersion": "2.0",
            "messageCount": 5,
            "totalTokensUsed": 1000,
        }
    )
    body = json.dumps(
        {
            "messages": [{"type": "human", "content": "ignored"}],
            "name": "renamed",
        }
    )
    resp = put_session(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 200, resp["body"]
    item = aws.sessions.get_item(Key={"sessionId": "test-session", "userId": "test-user"})["Item"]
    assert item["name"] == "renamed"
    # totalTokensUsed must be untouched on the v2 path
    assert int(item["totalTokensUsed"]) == 1000
    assert int(item["messageCount"]) == 5
    # history was not written
    assert "history" not in item


# --- compact_session ---


def _mock_summarization_call(content="SUMMARY-OK"):
    """Patch the http call inside compact_session to return a valid summary."""
    return patch(
        "session.lambda_functions.http_requests.post",
        return_value=SimpleNamespace(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": content}}]},
            text=content,
        ),
    )


def test_compact_session_returns_400_for_too_short(aws, lambda_context):
    aws.sessions.put_item(
        Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0", "messageCount": 1}
    )
    body = json.dumps({"modelId": "m1", "contextWindow": 8000})
    resp = compact_session(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 400
    assert "too short" in resp["body"]


def test_compact_session_returns_404_for_missing_session(aws, lambda_context):
    body = json.dumps({"modelId": "m1", "contextWindow": 8000})
    resp = compact_session(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 404


def test_compact_session_returns_500_when_no_messages_table(aws, lambda_context):
    with patch.object(lambda_functions, "messages_table", None):
        resp = compact_session(_claim_event(body=json.dumps({"modelId": "m", "contextWindow": 1})), lambda_context)
    assert resp["statusCode"] == 500


def test_compact_session_invalid_json_400(aws, lambda_context):
    resp = compact_session(_claim_event(body="not-json"), lambda_context)
    assert resp["statusCode"] == 400


def test_compact_session_validation_error_400(aws, lambda_context):
    resp = compact_session(_claim_event(body=json.dumps({})), lambda_context)
    assert resp["statusCode"] == 400


def test_compact_session_succeeds(aws, lambda_context):
    aws.sessions.put_item(
        Item={
            "sessionId": "test-session",
            "userId": "test-user",
            "storageVersion": "2.0",
            "messageCount": 3,
        }
    )
    aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": 0, "type": "system", "content": "sys"})
    aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": 1, "type": "human", "content": "q1"})
    aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": 2, "type": "ai", "content": "a1"})

    body = json.dumps({"modelId": "m1", "contextWindow": 8000})
    with _mock_summarization_call("compact-summary"), patch(
        "session.lambda_functions.get_rest_api_container_endpoint", return_value="http://serve"
    ), patch("session.lambda_functions.get_cert_path", return_value=False), patch(
        "session.lambda_functions.boto3.client"
    ):
        resp = compact_session(_claim_event(body=body), lambda_context)

    assert resp["statusCode"] == 200, resp["body"]
    body_resp = json.loads(resp["body"])
    assert body_resp["summaryContent"] == "compact-summary"
    # Summary persisted at index 3
    summary = aws.messages.get_item(Key={"sessionId": "test-session", "messageIndex": 3})["Item"]
    assert summary["type"] == "summary"
    # Sessions table updated
    sess = aws.sessions.get_item(Key={"sessionId": "test-session", "userId": "test-user"})["Item"]
    assert int(sess["compactionMessageIndex"]) == 3
    assert int(sess["tokensUsedSinceCompaction"]) == 0
    assert "compactedSystemPrompt" in sess


def test_compact_session_502_when_summarization_status_not_200(aws, lambda_context):
    aws.sessions.put_item(
        Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0", "messageCount": 3}
    )
    for i, t in enumerate(["system", "human", "ai"]):
        aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": i, "type": t, "content": "x"})

    body = json.dumps({"modelId": "m1", "contextWindow": 8000})
    failed = SimpleNamespace(status_code=503, json=lambda: {}, text="upstream down")
    with patch("session.lambda_functions.http_requests.post", return_value=failed), patch(
        "session.lambda_functions.get_rest_api_container_endpoint", return_value="http://serve"
    ), patch("session.lambda_functions.get_cert_path", return_value=False), patch(
        "session.lambda_functions.boto3.client"
    ):
        resp = compact_session(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 502


def test_compact_session_502_on_invalid_json_response(aws, lambda_context):
    aws.sessions.put_item(
        Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0", "messageCount": 3}
    )
    for i, t in enumerate(["system", "human", "ai"]):
        aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": i, "type": t, "content": "x"})

    body = json.dumps({"modelId": "m1", "contextWindow": 8000})

    def raise_invalid_json():
        raise ValueError("bad json")

    bad_resp = SimpleNamespace(status_code=200, json=raise_invalid_json, text="garbage")
    with patch("session.lambda_functions.http_requests.post", return_value=bad_resp), patch(
        "session.lambda_functions.get_rest_api_container_endpoint", return_value="http://serve"
    ), patch("session.lambda_functions.get_cert_path", return_value=False), patch(
        "session.lambda_functions.boto3.client"
    ):
        resp = compact_session(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 502


def test_compact_session_502_on_empty_summary_content(aws, lambda_context):
    aws.sessions.put_item(
        Item={"sessionId": "test-session", "userId": "test-user", "storageVersion": "2.0", "messageCount": 3}
    )
    for i, t in enumerate(["system", "human", "ai"]):
        aws.messages.put_item(Item={"sessionId": "test-session", "messageIndex": i, "type": t, "content": "x"})

    body = json.dumps({"modelId": "m1", "contextWindow": 8000})
    with _mock_summarization_call("   "), patch(
        "session.lambda_functions.get_rest_api_container_endpoint", return_value="http://serve"
    ), patch("session.lambda_functions.get_cert_path", return_value=False), patch(
        "session.lambda_functions.boto3.client"
    ):
        resp = compact_session(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 502


def test_compact_session_auto_migrates_legacy_session(aws, lambda_context):
    """Legacy v1.0 sessions should be migrated and then compacted."""
    aws.sessions.put_item(
        Item={
            "sessionId": "test-session",
            "userId": "test-user",
            "history": [
                {"type": "system", "content": "sys"},
                {"type": "human", "content": "q1"},
                {"type": "ai", "content": "a1"},
            ],
        }
    )
    body = json.dumps({"modelId": "m1", "contextWindow": 8000})
    with _mock_summarization_call(), patch(
        "session.lambda_functions.get_rest_api_container_endpoint", return_value="http://serve"
    ), patch("session.lambda_functions.get_cert_path", return_value=False), patch(
        "session.lambda_functions.boto3.client"
    ):
        resp = compact_session(_claim_event(body=body), lambda_context)
    assert resp["statusCode"] == 200, resp["body"]
