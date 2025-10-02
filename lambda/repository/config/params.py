"""Parameter extraction and validation for pagination requests."""

import json
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional

from utilities.types import PaginationParams
from utilities.validation import ValidationError
from utilities.constants import (
    DEFAULT_TIME_LIMIT_HOURS,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
)


@dataclass  
class ListJobsParams:
    """Parameters for listing ingestion jobs."""
    repository_id: str
    page_size: int = 10
    last_evaluated_key: Optional[Dict[str, Any]] = None
    time_limit_hours: int = DEFAULT_TIME_LIMIT_HOURS
    
    @classmethod
    def from_event(cls, event: Dict[str, Any]) -> 'ListJobsParams':
        """Extract and validate parameters from Lambda event."""
        path_params = event.get("pathParameters", {})
        query_params = event.get("queryStringParameters", {}) or {}
        
        repository_id = path_params.get("repositoryId")
        if not repository_id:
            raise ValidationError("repositoryId is required")
            
        return cls(
            repository_id=repository_id,
            time_limit_hours=cls._parse_time_limit(query_params),
            page_size=cls._parse_page_size(query_params),
            last_evaluated_key=cls._parse_last_evaluated_key(query_params)
        )
    
    @staticmethod
    def _parse_time_limit(query_params: Dict[str, str]) -> int:
        """Parse time limit from query parameters."""
        return int(query_params.get("timeLimit", str(DEFAULT_TIME_LIMIT_HOURS)))
    
    @staticmethod
    def _parse_page_size(query_params: Dict[str, str]) -> int:
        """Parse and validate page size from query parameters."""
        page_size = int(query_params.get("pageSize", str(DEFAULT_PAGE_SIZE)))
        return max(MIN_PAGE_SIZE, min(page_size, MAX_PAGE_SIZE))
    
    @staticmethod
    def _parse_last_evaluated_key(query_params: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Parse lastEvaluatedKey with specific error handling."""
        if "lastEvaluatedKey" not in query_params:
            return None
            
        try:
            decoded = urllib.parse.unquote(query_params["lastEvaluatedKey"])
            return json.loads(decoded)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON in lastEvaluatedKey: {e}")
        except (TypeError, ValueError) as e:
            raise ValidationError(f"Invalid lastEvaluatedKey format: {e}")
