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
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

# Prevent lambda/models imports from failing during autouse fixtures.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("MODEL_TABLE_NAME", "model-table")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "guardrails-table")
os.environ.setdefault("SESSIONS_BY_USER_ID_INDEX_NAME", "byUserId")

from lisa.session.repository import (  # noqa: E402
    build_message_item,
    decrypt_message_in_place,
    delete_session_messages,
    delete_user_session,
    extract_video_s3_keys,
    get_all_user_sessions,
    migrate_session_to_v2,
    put_message_with_index_retry,
    query_session_messages,
)
from lisa.utilities.session_encryption import SessionEncryptionError  # noqa: E402


@pytest.fixture
def aws_creds():
    """Set mock AWS creds before any moto context."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture
def messages_table(aws_creds):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="session-messages",
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
        table.wait_until_exists()
        yield table, dynamodb


@pytest.fixture
def sessions_table(aws_creds):
    """Create a sessions table whose GSI matches whatever the environment
    expects — earlier tests in the suite may have set
    ``SESSIONS_BY_USER_ID_INDEX_NAME`` to a different value, and the repository
    helper reads it at call time."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        index_name = os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"]
        table = dynamodb.create_table(
            TableName="sessions",
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
                    "IndexName": index_name,
                    "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


# --- get_all_user_sessions ---


def test_get_all_user_sessions_returns_items(sessions_table):
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1", "name": "first"})
    sessions_table.put_item(Item={"sessionId": "s2", "userId": "u1", "name": "second"})
    sessions_table.put_item(Item={"sessionId": "s3", "userId": "other", "name": "other"})

    items = get_all_user_sessions(sessions_table, "u1")
    assert len(items) == 2


def test_get_all_user_sessions_with_projection(sessions_table):
    sessions_table.put_item(
        Item={"sessionId": "s1", "userId": "u1", "name": "first", "history": [{"big": "blob"}] * 100}
    )
    items = get_all_user_sessions(
        sessions_table,
        "u1",
        projection_expression="sessionId, userId, #n",
        expression_attribute_names={"#n": "name"},
    )
    assert len(items) == 1
    # Projection shouldn't include `history`
    assert "history" not in items[0]
    assert items[0]["name"] == "first"


def test_get_all_user_sessions_swallows_resource_not_found():
    """Helper logs and returns empty when the table doesn't exist."""
    bad_table = MagicMock()
    bad_table.query.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}},
        operation_name="Query",
    )
    items = get_all_user_sessions(bad_table, "u1")
    assert items == []


def test_get_all_user_sessions_swallows_other_client_errors():
    bad_table = MagicMock()
    bad_table.query.side_effect = ClientError(
        error_response={"Error": {"Code": "ThrottlingException"}},
        operation_name="Query",
    )
    # Logged + returns empty (not raised)
    items = get_all_user_sessions(bad_table, "u1")
    assert items == []


# --- extract_video_s3_keys ---


def test_extract_video_s3_keys_pulls_keys_from_history():
    session = {
        "history": [
            {"content": "hi"},  # plain string content — skipped
            {
                "content": [
                    {"type": "text", "text": "look"},
                    {"type": "video_url", "video_url": {"s3_key": "v1.mp4"}},
                    {"type": "video_url", "video_url": {}},  # missing key — skipped
                    {"type": "image_url", "image_url": {"s3_key": "i1.png"}},  # not video — skipped
                ]
            },
            {
                "content": [
                    {"type": "video_url", "video_url": {"s3_key": "v2.mp4"}},
                ]
            },
        ]
    }
    keys = extract_video_s3_keys(session)
    assert sorted(keys) == ["v1.mp4", "v2.mp4"]


def test_extract_video_s3_keys_empty_history_returns_empty():
    assert extract_video_s3_keys({}) == []


# --- delete_session_messages ---


def test_delete_session_messages_no_op_when_no_table(aws_creds):
    """Falsy table short-circuits; never touches dynamodb_resource."""
    delete_session_messages(None, MagicMock(), "s1")
    delete_session_messages(False, MagicMock(), "s1")  # type: ignore[arg-type]


def test_delete_session_messages_deletes_all_for_session(messages_table):
    table, dynamodb = messages_table
    for i in range(5):
        table.put_item(Item={"sessionId": "s1", "messageIndex": i, "content": f"m{i}"})
    table.put_item(Item={"sessionId": "s2", "messageIndex": 0, "content": "other"})

    delete_session_messages(table, dynamodb, "s1")

    remaining = table.scan().get("Items", [])
    # Only the s2 message should remain
    assert len(remaining) == 1
    assert remaining[0]["sessionId"] == "s2"


def test_delete_session_messages_handles_query_client_error():
    table = MagicMock()
    table.name = "msg-table"
    table.query.side_effect = ClientError(
        error_response={"Error": {"Code": "ProvisionedThroughputExceededException"}},
        operation_name="Query",
    )
    # Should swallow, not raise
    delete_session_messages(table, MagicMock(), "s1")


def test_delete_session_messages_handles_batch_write_failure(messages_table):
    """A failing batch_write_item is logged but the loop still completes."""
    table, dynamodb = messages_table
    table.put_item(Item={"sessionId": "s1", "messageIndex": 0, "content": "m0"})
    failing = MagicMock()
    failing.meta.client.batch_write_item.side_effect = ClientError(
        error_response={"Error": {"Code": "InternalServerError"}},
        operation_name="BatchWriteItem",
    )
    # No raise — the helper logs and returns
    delete_session_messages(table, failing, "s1")


def test_delete_session_messages_retries_unprocessed_items(messages_table):
    """When batch_write_item returns UnprocessedItems (no exception), the helper must
    retry until they're all processed. Without retry, throttled deletes silently
    leave orphan rows."""
    table, _ = messages_table
    for i in range(3):
        table.put_item(Item={"sessionId": "s1", "messageIndex": i, "content": f"m{i}"})

    fake_dynamodb = MagicMock()
    table_name = table.name
    # First call returns one of the three back as UnprocessedItems; second clears.
    fake_dynamodb.meta.client.batch_write_item.side_effect = [
        {
            "UnprocessedItems": {
                table_name: [
                    {"DeleteRequest": {"Key": {"sessionId": "s1", "messageIndex": 1}}},
                ]
            }
        },
        {"UnprocessedItems": {}},
    ]
    # Speed the test up by suppressing real sleeps
    with patch("lisa.session.repository.time.sleep"):
        delete_session_messages(table, fake_dynamodb, "s1")
    # Two calls because the first response had unprocessed items
    assert fake_dynamodb.meta.client.batch_write_item.call_count == 2


def test_delete_session_messages_gives_up_after_max_unprocessed_retries(messages_table):
    """Persistent UnprocessedItems should not cause an infinite loop or a raise."""
    table, _ = messages_table
    table.put_item(Item={"sessionId": "s1", "messageIndex": 0, "content": "m0"})

    fake_dynamodb = MagicMock()
    table_name = table.name
    # Always return the same unprocessed item — should give up after 5 attempts
    fake_dynamodb.meta.client.batch_write_item.return_value = {
        "UnprocessedItems": {
            table_name: [
                {"DeleteRequest": {"Key": {"sessionId": "s1", "messageIndex": 0}}},
            ]
        }
    }
    with patch("lisa.session.repository.time.sleep"):
        # Must not raise
        delete_session_messages(table, fake_dynamodb, "s1")
    assert fake_dynamodb.meta.client.batch_write_item.call_count == 5


# --- delete_user_session ---


def test_delete_user_session_removes_session_and_skips_s3_when_bucket_missing(sessions_table):
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1", "history": []})
    s3_resource = MagicMock()
    s3_client = MagicMock()
    resp = delete_user_session(sessions_table, s3_resource, s3_client, "", "s1", "u1")
    assert resp.deleted is True
    # S3 not invoked
    s3_resource.Bucket.assert_not_called()
    # Session removed
    assert sessions_table.get_item(Key={"sessionId": "s1", "userId": "u1"}).get("Item") is None


def test_delete_user_session_calls_delete_session_messages_when_v2(sessions_table, messages_table):
    msg_table, dynamodb = messages_table
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1", "history": []})
    msg_table.put_item(Item={"sessionId": "s1", "messageIndex": 0, "content": "m0"})
    s3_resource = MagicMock()
    resp = delete_user_session(
        sessions_table,
        s3_resource,
        MagicMock(),
        "",
        "s1",
        "u1",
        messages_table=msg_table,
        dynamodb_resource=dynamodb,
    )
    assert resp.deleted is True
    # Messages purged
    assert msg_table.scan().get("Items") == []


def test_delete_user_session_swallows_resource_not_found():
    table = MagicMock()
    table.get_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}},
        operation_name="GetItem",
    )
    resp = delete_user_session(table, MagicMock(), MagicMock(), "", "s1", "u1")
    assert resp.deleted is False


def test_delete_user_session_decryption_failure_logged_but_continues(sessions_table):
    """If decrypting an encrypted session fails, the rest of the cleanup still runs."""
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1", "is_encrypted": True})
    with patch("lisa.session.repository.decrypt_session_fields") as mock_decrypt:
        mock_decrypt.side_effect = SessionEncryptionError("kms down")
        resp = delete_user_session(sessions_table, MagicMock(), MagicMock(), "", "s1", "u1")
    assert resp.deleted is True


def test_delete_user_session_deletes_videos_from_s3(sessions_table):
    sessions_table.put_item(
        Item={
            "sessionId": "s1",
            "userId": "u1",
            "history": [
                {"content": [{"type": "video_url", "video_url": {"s3_key": "v1.mp4"}}]},
            ],
        }
    )
    s3_resource = MagicMock()
    s3_client = MagicMock()
    resp = delete_user_session(sessions_table, s3_resource, s3_client, "test-bucket", "s1", "u1")
    assert resp.deleted is True
    # Image-prefix delete invoked, plus video s3 delete
    s3_resource.Bucket.assert_called_with("test-bucket")
    s3_client.delete_object.assert_called_with(Bucket="test-bucket", Key="v1.mp4")


def test_delete_user_session_video_delete_failure_does_not_abort(sessions_table):
    sessions_table.put_item(
        Item={
            "sessionId": "s1",
            "userId": "u1",
            "history": [{"content": [{"type": "video_url", "video_url": {"s3_key": "v1.mp4"}}]}],
        }
    )
    s3_client = MagicMock()
    s3_client.delete_object.side_effect = ClientError(
        error_response={"Error": {"Code": "InternalServerError"}},
        operation_name="DeleteObject",
    )
    resp = delete_user_session(sessions_table, MagicMock(), s3_client, "bucket", "s1", "u1")
    # Deletion of session row still succeeded
    assert resp.deleted is True


# --- decrypt_message_in_place ---


def test_decrypt_message_in_place_no_op_when_not_encrypted():
    msg = {"content": "plaintext", "is_encrypted": False}
    decrypt_message_in_place(msg, "u1", "s1")
    assert msg["content"] == "plaintext"


def test_decrypt_message_in_place_no_op_when_no_content():
    msg = {"is_encrypted": True}
    decrypt_message_in_place(msg, "u1", "s1")
    # No mutation; no exception


def test_decrypt_message_in_place_unwraps_dict_payload():
    msg = {"is_encrypted": True, "content": "ciphertext-blob"}
    payload = {"content": "decrypted text", "metadata": {"k": "v"}, "reasoningContent": "thoughts"}
    with patch("lisa.session.repository.decrypt_session_data", return_value=payload):
        decrypt_message_in_place(msg, "u1", "s1")
    assert msg["content"] == "decrypted text"
    assert msg["metadata"] == {"k": "v"}
    assert msg["reasoningContent"] == "thoughts"
    assert "is_encrypted" not in msg


def test_decrypt_message_in_place_legacy_string_payload():
    msg = {"is_encrypted": True, "content": "ciphertext"}
    with patch("lisa.session.repository.decrypt_session_data", return_value="just plain text"):
        decrypt_message_in_place(msg, "u1", "s1")
    assert msg["content"] == "just plain text"
    assert "is_encrypted" not in msg


def test_decrypt_message_in_place_swallows_decryption_failure():
    msg = {"is_encrypted": True, "content": "ciphertext", "messageIndex": 5}
    with patch("lisa.session.repository.decrypt_session_data", side_effect=Exception("kms down")):
        decrypt_message_in_place(msg, "u1", "s1")
    # Untouched on failure
    assert msg["content"] == "ciphertext"
    assert msg["is_encrypted"] is True


# --- build_message_item ---


def test_build_message_item_plaintext_strips_falsy_optional_fields():
    msg = {"type": "human", "content": "hi", "metadata": {}, "reasoningContent": "", "toolCalls": []}
    item = build_message_item("s1", 0, msg, encryption_enabled=False, user_id="u1", default_created_at="2024-01-01")
    assert item["sessionId"] == "s1"
    assert item["messageIndex"] == 0
    assert item["type"] == "human"
    assert item["content"] == "hi"
    assert item["createdAt"] == "2024-01-01"
    assert "metadata" not in item
    assert "reasoningContent" not in item
    assert "toolCalls" not in item


def test_build_message_item_uses_msg_created_at_when_present():
    msg = {"type": "human", "content": "hi", "createdAt": "actual-ts"}
    item = build_message_item("s1", 0, msg, encryption_enabled=False, user_id="u1", default_created_at="fallback")
    assert item["createdAt"] == "actual-ts"


def test_build_message_item_plaintext_includes_optional_fields_when_truthy():
    msg = {
        "type": "ai",
        "content": "hello",
        "metadata": {"k": "v"},
        "reasoningContent": "thoughts",
        "toolCalls": [{"name": "t"}],
        "usage": {"promptTokens": 5},
        "guardrailTriggered": True,
        "reasoningSignature": "sig",
    }
    item = build_message_item("s1", 1, msg, encryption_enabled=False, user_id="u1", default_created_at="ts")
    assert item["metadata"] == {"k": "v"}
    assert item["reasoningContent"] == "thoughts"
    assert item["toolCalls"] == [{"name": "t"}]
    assert item["usage"] == {"promptTokens": 5}
    assert item["guardrailTriggered"] is True
    assert item["reasoningSignature"] == "sig"


def test_build_message_item_guardrail_false_kept():
    """``guardrailTriggered=False`` is not None — it should be preserved."""
    msg = {"type": "ai", "content": "ok", "guardrailTriggered": False}
    item = build_message_item("s1", 0, msg, encryption_enabled=False, user_id="u1", default_created_at="ts")
    assert item["guardrailTriggered"] is False


def test_build_message_item_encrypted_bundles_sensitive_fields():
    msg = {"type": "human", "content": "secret", "metadata": {"m": 1}, "reasoningContent": "rc"}
    with patch("lisa.session.repository.encrypt_session_data", return_value="encrypted-blob") as mock_enc:
        item = build_message_item("s1", 0, msg, encryption_enabled=True, user_id="u1", default_created_at="ts")
    assert item["content"] == "encrypted-blob"
    assert item["is_encrypted"] is True
    # Sensitive fields are NOT stored at top level
    assert "metadata" not in item
    assert "reasoningContent" not in item
    # And the bundle passed to encrypt_session_data carried them
    bundled = mock_enc.call_args[0][0]
    assert bundled["content"] == "secret"
    assert bundled["metadata"] == {"m": 1}
    assert bundled["reasoningContent"] == "rc"


def test_build_message_item_default_type_human():
    item = build_message_item("s1", 0, {"content": "no-type"}, False, "u1", "ts")
    assert item["type"] == "human"


# --- put_message_with_index_retry ---


def test_put_message_with_index_retry_writes_at_starting_index(messages_table):
    table, _ = messages_table
    idx = put_message_with_index_retry(
        table,
        "s1",
        "u1",
        {"type": "human", "content": "hi"},
        encryption_enabled=False,
        starting_index=0,
        default_created_at="ts",
    )
    assert idx == 0
    item = table.get_item(Key={"sessionId": "s1", "messageIndex": 0}).get("Item")
    assert item is not None


def test_put_message_with_index_retry_collides_then_succeeds(messages_table):
    """When the starting index is taken, helper retries at a higher index."""
    table, _ = messages_table
    table.put_item(Item={"sessionId": "s1", "messageIndex": 0, "content": "existing"})

    idx = put_message_with_index_retry(
        table,
        "s1",
        "u1",
        {"type": "human", "content": "hi"},
        encryption_enabled=False,
        starting_index=0,
        default_created_at="ts",
    )
    # Retried at the next free slot; current_count is 1 so candidate becomes max(1, 1) = 1
    assert idx == 1


def test_put_message_with_index_retry_raises_after_max_attempts():
    table = MagicMock()
    table.put_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ConditionalCheckFailedException"}},
        operation_name="PutItem",
    )
    table.query.return_value = {"Count": 0}
    with pytest.raises(RuntimeError):
        put_message_with_index_retry(
            table,
            "s1",
            "u1",
            {"type": "human", "content": "hi"},
            False,
            0,
            "ts",
            max_attempts=2,
        )


def test_put_message_with_index_retry_propagates_non_collision_errors():
    table = MagicMock()
    table.put_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}},
        operation_name="PutItem",
    )
    with pytest.raises(ClientError):
        put_message_with_index_retry(
            table,
            "s1",
            "u1",
            {"type": "human", "content": "hi"},
            False,
            0,
            "ts",
        )


def test_put_message_with_index_retry_no_table_raises():
    with pytest.raises(RuntimeError):
        put_message_with_index_retry(None, "s1", "u1", {"content": "x"}, False, 0, "ts")


# --- query_session_messages ---


def test_query_session_messages_returns_ascending(messages_table):
    table, _ = messages_table
    table.put_item(Item={"sessionId": "s1", "messageIndex": 2, "type": "ai", "content": "third"})
    table.put_item(Item={"sessionId": "s1", "messageIndex": 0, "type": "human", "content": "first"})
    table.put_item(Item={"sessionId": "s1", "messageIndex": 1, "type": "ai", "content": "second"})

    msgs = query_session_messages(table, "s1", "u1")
    assert [int(m["messageIndex"]) for m in msgs] == [0, 1, 2]


def test_query_session_messages_with_start_index_filter(messages_table):
    table, _ = messages_table
    for i in range(5):
        table.put_item(Item={"sessionId": "s1", "messageIndex": i, "content": f"m{i}"})
    msgs = query_session_messages(table, "s1", "u1", start_index=2)
    assert [int(m["messageIndex"]) for m in msgs] == [2, 3, 4]


def test_query_session_messages_decrypts_each_message(messages_table):
    table, _ = messages_table
    table.put_item(
        Item={"sessionId": "s1", "messageIndex": 0, "type": "human", "content": "blob", "is_encrypted": True}
    )
    with patch("lisa.session.repository.decrypt_session_data", return_value={"content": "plain"}):
        msgs = query_session_messages(table, "s1", "u1")
    assert msgs[0]["content"] == "plain"
    assert "is_encrypted" not in msgs[0]


def test_query_session_messages_no_table_raises():
    with pytest.raises(RuntimeError):
        query_session_messages(None, "s1", "u1")


# --- migrate_session_to_v2 ---


def test_migrate_session_to_v2_no_history_just_flips_storage_version(sessions_table, messages_table):
    msg_table, _ = messages_table
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1"})
    count = migrate_session_to_v2(
        sessions_table,
        msg_table,
        "s1",
        "u1",
        {"messageCount": 0},
        encryption_enabled=False,
        timestamp="ts",
    )
    assert count == 0
    item = sessions_table.get_item(Key={"sessionId": "s1", "userId": "u1"}).get("Item")
    assert item["storageVersion"] == "2.0"


def test_migrate_session_to_v2_writes_messages_and_clears_history(sessions_table, messages_table):
    msg_table, _ = messages_table
    history = [
        {"type": "human", "content": "hi"},
        {"type": "ai", "content": "hello"},
    ]
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1", "history": history})
    count = migrate_session_to_v2(
        sessions_table,
        msg_table,
        "s1",
        "u1",
        {"history": history, "startTime": "t0"},
        encryption_enabled=False,
        timestamp="ts",
    )
    assert count == 2
    # Messages migrated
    msgs = msg_table.scan().get("Items", [])
    assert len(msgs) == 2
    # Session was updated: history removed, storageVersion 2.0
    item = sessions_table.get_item(Key={"sessionId": "s1", "userId": "u1"}).get("Item")
    assert item["storageVersion"] == "2.0"
    assert "history" not in item


def test_migrate_session_to_v2_handles_encrypted_history(sessions_table, messages_table):
    msg_table, _ = messages_table
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1", "encrypted_history": "blob", "is_encrypted": True})
    decrypted_history = [{"type": "human", "content": "secret"}]
    with patch(
        "lisa.session.repository.decrypt_session_fields",
        return_value={"history": decrypted_history},
    ):
        count = migrate_session_to_v2(
            sessions_table,
            msg_table,
            "s1",
            "u1",
            {"encrypted_history": "blob", "is_encrypted": True},
            encryption_enabled=False,
            timestamp="ts",
        )
    assert count == 1


def test_migrate_session_to_v2_decryption_failure_propagates():
    bad_session_table = MagicMock()
    bad_msg_table = MagicMock()
    with patch(
        "lisa.session.repository.decrypt_session_fields",
        side_effect=SessionEncryptionError("kms down"),
    ):
        with pytest.raises(SessionEncryptionError):
            migrate_session_to_v2(
                bad_session_table,
                bad_msg_table,
                "s1",
                "u1",
                {"encrypted_history": "blob"},
                encryption_enabled=False,
                timestamp="ts",
            )


def test_migrate_session_to_v2_no_table_raises():
    with pytest.raises(RuntimeError):
        migrate_session_to_v2(MagicMock(), None, "s1", "u1", {}, False, "ts")


def test_migrate_session_to_v2_partial_index_collision_logged(sessions_table, messages_table):
    """If a message index is already populated (from a prior partial migration), the helper logs and continues."""
    msg_table, _ = messages_table
    msg_table.put_item(Item={"sessionId": "s1", "messageIndex": 0, "content": "already migrated"})
    history = [{"type": "human", "content": "hi"}, {"type": "ai", "content": "hello"}]
    sessions_table.put_item(Item={"sessionId": "s1", "userId": "u1", "history": history})

    count = migrate_session_to_v2(
        sessions_table,
        msg_table,
        "s1",
        "u1",
        {"history": history},
        encryption_enabled=False,
        timestamp="ts",
    )
    # Helper returns total messages it tried to migrate, not just newly-written ones
    assert count == 2
