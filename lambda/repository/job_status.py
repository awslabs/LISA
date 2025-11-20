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

"""Job status helper functions."""

from models.domain_objects import IngestionStatus


def is_terminal_status(status: IngestionStatus) -> bool:
    """Check if status is terminal."""
    return status in [
        IngestionStatus.INGESTION_COMPLETED,
        IngestionStatus.INGESTION_FAILED,
        IngestionStatus.DELETE_COMPLETED,
        IngestionStatus.DELETE_FAILED,
    ]


def is_success_status(status: IngestionStatus) -> bool:
    """Check if status is success."""
    return status in [
        IngestionStatus.INGESTION_COMPLETED,
        IngestionStatus.DELETE_COMPLETED,
    ]
