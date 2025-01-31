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

import json
import logging
import os

logger = logging.getLogger(__name__)


class RagVectorStoreRepository:
    """RAG Vector Store repository"""

    def __init__(self) -> None:
        self.repositories = json.loads(os.environ.get("REPOSITORY_CONFIG", "[]"))

    def find_pipeline_config(self, repository_id: str, pipeline_id: str) -> dict:
        """Find pipeline config"""
        # TODO: Replace with Vector Store DB lookup when available
        repository: dict = next((r for r in self.repositories if r.get("repositoryId") == repository_id), {})
        pipelines = repository.get("pipelines", [])
        pipeline: dict = next((p for p in pipelines if p.get("embeddingModel") == pipeline_id), {})
        return pipeline
