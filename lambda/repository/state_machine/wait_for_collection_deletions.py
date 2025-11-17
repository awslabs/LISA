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

"""Wait for all collection deletion jobs to complete before deleting repository."""

import logging
import os
from typing import Any, Dict

from repository.ingestion_job_repo import IngestionJobRepository

logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Check if all collection deletion jobs for a repository are complete.

    Args:
        event: Event data containing repositoryId and stackName
        context: Lambda context

    Returns:
        Dictionary with completion status and job counts
    """
    repository_id = event.get("repositoryId")
    stack_name = event.get("stackName")

    logger.info(f"Checking collection deletion jobs for repository {repository_id}")

    job_repo = IngestionJobRepository()

    # Query all jobs for this repository
    pending_jobs = job_repo.find_pending_collection_deletions(repository_id)

    pending_count = len(pending_jobs)
    all_complete = pending_count == 0

    logger.info(
        f"Repository {repository_id}: "
        f"pending_collection_deletions={pending_count}, "
        f"all_complete={all_complete}"
    )

    return {
        "repositoryId": repository_id,
        "stackName": stack_name,
        "allCollectionDeletionsComplete": all_complete,
        "pendingDeletionCount": pending_count,
    }
