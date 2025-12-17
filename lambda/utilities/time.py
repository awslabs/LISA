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

from datetime import datetime, timezone


def now(tz=timezone.utc) -> int:
    """Return UTC epoch milliseconds."""
    return int(datetime.now(tz).timestamp() * 1000)


def now_seconds(tz=timezone.utc) -> int:
    """Return UTC epoch seconds."""
    return int(datetime.now(tz).timestamp())


def iso_string(tz=timezone.utc) -> str:
    """Return ISO datetime string with UTC offset."""
    return datetime.now(tz).isoformat()


def utc_now() -> datetime:
    """Return current UTC datetime object."""
    return datetime.now(timezone.utc)
