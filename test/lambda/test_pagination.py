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

import base64
import json
import os
from decimal import Decimal

import pytest

# Prevent lambda/models imports from failing during autouse fixtures.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("MODEL_TABLE_NAME", "model-table")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "guardrails-table")

from lisa.utilities.pagination import decode_cursor, encode_cursor  # noqa: E402


def test_encode_cursor_returns_url_safe_base64():
    cursor = encode_cursor({"sessionId": "s1", "messageIndex": 5})
    # Should be decodable as URL-safe base64
    raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
    parsed = json.loads(raw)
    assert parsed["sessionId"] == "s1"
    assert parsed["messageIndex"] == 5


def test_decode_cursor_round_trip_int_index():
    original = {"sessionId": "s1", "messageIndex": 7}
    decoded = decode_cursor(encode_cursor(original))
    assert decoded["sessionId"] == "s1"
    # decode forces messageIndex to Decimal so DynamoDB queries see the right type
    assert decoded["messageIndex"] == Decimal("7")
    assert isinstance(decoded["messageIndex"], Decimal)


def test_decode_cursor_round_trip_decimal_index():
    """Decimal values from DynamoDB must round-trip without losing precision."""
    original = {"sessionId": "s2", "messageIndex": Decimal("42")}
    cursor = encode_cursor(original)
    decoded = decode_cursor(cursor)
    assert decoded["messageIndex"] == Decimal("42")
    assert isinstance(decoded["messageIndex"], Decimal)


def test_decode_cursor_without_message_index():
    """Cursors without messageIndex should still decode (no coercion)."""
    cursor = encode_cursor({"sessionId": "s3", "userId": "u3"})
    decoded = decode_cursor(cursor)
    assert decoded == {"sessionId": "s3", "userId": "u3"}
    assert "messageIndex" not in decoded


def test_decode_cursor_invalid_base64_raises():
    with pytest.raises(Exception):
        decode_cursor("not-valid-base64!!!@@@")


def test_decode_cursor_invalid_json_raises():
    """Valid base64 with non-JSON contents should raise."""
    bad = base64.urlsafe_b64encode(b"not json").decode("utf-8")
    with pytest.raises(Exception):
        decode_cursor(bad)


def test_encode_cursor_handles_nested_decimal():
    """convert_decimal flattens nested Decimals so json.dumps does not fail."""
    cursor = encode_cursor({"sessionId": "s4", "messageIndex": Decimal("1"), "meta": {"score": Decimal("0.5")}})
    decoded = decode_cursor(cursor)
    assert decoded["meta"]["score"] == Decimal("0.5")
