"""Pagination-related data models and results."""

from dataclasses import dataclass
from typing import Dict, Optional
from utilities.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
)


@dataclass
class PaginationResult:
    """Result of pagination analysis."""
    has_next_page: bool
    has_previous_page: bool
    
    @classmethod
    def from_keys(cls, 
                  original_key: Optional[Dict[str, str]], 
                  returned_key: Optional[Dict[str, str]]) -> 'PaginationResult':
        """Create pagination result from keys."""
        return cls(
            has_next_page=returned_key is not None,
            has_previous_page=original_key is not None
        )

@dataclass
class PaginationParams:
    """Shared pagination parameter handling."""
    
    page_size: int = DEFAULT_PAGE_SIZE
    last_evaluated_key: Optional[Dict[str, str]] = None
    
    @staticmethod
    def parse_page_size(query_params: Dict[str, str], 
                       default: int = DEFAULT_PAGE_SIZE,
                       max_size: int = MAX_PAGE_SIZE) -> int:
        """Parse and validate page size with configurable limits."""
        page_size = int(query_params.get("pageSize", str(default)))
        return max(MIN_PAGE_SIZE, min(page_size, max_size))
