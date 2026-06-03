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

"""Opaque base64 cursor helpers for DynamoDB cursor-based pagination."""

import base64
import json
from decimal import Decimal
from typing import Any

from lisa.utilities.encoders import convert_decimal


def encode_cursor(last_evaluated_key: dict[str, Any]) -> str:
    """Encode a DynamoDB ``LastEvaluatedKey`` as an opaque base64 cursor."""
    serializable = convert_decimal(last_evaluated_key)
    return base64.urlsafe_b64encode(json.dumps(serializable).encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a base64 cursor back into a DynamoDB ``ExclusiveStartKey``.

    ``messageIndex`` is re-coerced to ``Decimal`` because DynamoDB Number
    attributes round-trip as ``Decimal``.
    """
    decoded: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"),
        parse_float=Decimal,
    )
    if "messageIndex" in decoded:
        decoded["messageIndex"] = Decimal(str(decoded["messageIndex"]))
    return decoded
