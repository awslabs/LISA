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

#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Repository service for vector store operations."""

from typing import Any, cast, Dict, List

from repository.vector_store_repo import VectorStoreRepository

_vs_repo = VectorStoreRepository()


def get_repository(repository_id: str) -> Dict[str, Any]:
    """Get a repository by ID."""
    return cast(Dict[str, Any], _vs_repo.find_repository_by_id(repository_id))


def list_repositories() -> List[Dict[str, Any]]:
    """List all repositories."""
    return cast(List[Dict[str, Any]], _vs_repo.get_registered_repositories())


def get_repository_status() -> Dict[str, str]:
    """Get status of all repositories."""
    return cast(Dict[str, str], _vs_repo.get_repository_status())


def save_repository(repo_data: Dict[str, Any]) -> None:
    """Save a repository."""
    repository_id = repo_data.get("repositoryId")
    if not repository_id:
        raise ValueError("repositoryId is required")
    _vs_repo.update(repository_id, repo_data)


def delete_repository(repository_id: str) -> None:
    """Delete a repository."""
    _vs_repo.delete(repository_id)
