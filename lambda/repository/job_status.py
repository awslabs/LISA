"""Pydantic models for job status responses."""

from pydantic import BaseModel


class JobStatus(BaseModel):
    """Job status details returned by list_jobs_by_repository."""
    
    status: str
    document: str
    auto: bool
    created_date: str