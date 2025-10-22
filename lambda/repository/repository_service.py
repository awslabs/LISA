#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Repository service for vector store operations."""

from typing import List, Dict, Any, Optional
from repository.vector_store_repo import VectorStoreRepository


_vs_repo = VectorStoreRepository()


def get_repository(repository_id: str) -> Dict[str, Any]:
    """Get a repository by ID."""
    return _vs_repo.find_repository_by_id(repository_id)


def list_repositories() -> List[Dict[str, Any]]:
    """List all repositories."""
    return _vs_repo.get_registered_repositories()


def get_repository_status() -> Dict[str, str]:
    """Get status of all repositories."""
    return _vs_repo.get_repository_status()


def save_repository(repo_data: Dict[str, Any]) -> None:
    """Save a repository."""
    repository_id = repo_data.get("repositoryId")
    if not repository_id:
        raise ValueError("repositoryId is required")
    _vs_repo.update(repository_id, repo_data)


def delete_repository(repository_id: str) -> None:
    """Delete a repository."""
    _vs_repo.delete(repository_id)
