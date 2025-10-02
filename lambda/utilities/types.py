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

"""Pagination-related data models and results."""

from dataclasses import dataclass
from typing import Dict, Optional

from utilities.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MIN_PAGE_SIZE


@dataclass
class PaginationResult:
    """Result of pagination analysis."""

    has_next_page: bool
    has_previous_page: bool

    @classmethod
    def from_keys(
        cls, original_key: Optional[Dict[str, str]], returned_key: Optional[Dict[str, str]]
    ) -> "PaginationResult":
        """Create pagination result from keys."""
        return cls(has_next_page=returned_key is not None, has_previous_page=original_key is not None)


@dataclass
class PaginationParams:
    """Shared pagination parameter handling."""

    page_size: int = DEFAULT_PAGE_SIZE
    last_evaluated_key: Optional[Dict[str, str]] = None

    @staticmethod
    def parse_page_size(
        query_params: Dict[str, str], default: int = DEFAULT_PAGE_SIZE, max_size: int = MAX_PAGE_SIZE
    ) -> int:
        """Parse and validate page size with configurable limits."""
        page_size = int(query_params.get("pageSize", str(default)))
        return max(MIN_PAGE_SIZE, min(page_size, max_size))
