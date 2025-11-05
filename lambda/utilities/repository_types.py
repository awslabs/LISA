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

from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class RepositoryType(str, Enum):
    PGVECTOR = "pgvector"
    OPENSEARCH = "opensearch"
    BEDROCK_KB = "bedrock_knowledge_base"

    @classmethod
    def get_type(cls, repository: Dict[str, Any]) -> RepositoryType:
        return RepositoryType(repository.get("type"))

    @classmethod
    def is_type(cls, repository: Dict[str, Any], repo_type: RepositoryType) -> bool:
        return repository.get("type") == repo_type

    def calculate_similarity_score(self, score: float) -> float:
        # Convert cosine distance to similarity for PGVector
        # PGVector returns cosine distance (0-2 range, lower = more similar)
        # Convert to similarity (0-1 range, higher = more similar)
        if self == RepositoryType.PGVECTOR:
            return max(0.0, 1.0 - (score / 2.0))
        else:
            return score
