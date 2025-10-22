#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

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
