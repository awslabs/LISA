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

"""Embedding prefix resolution and preset registry."""

from models.domain_objects import EmbeddingPrefixConfig, PrefixMode


class PrefixResolver:
    """Stateless utility for applying embedding prefix configuration to text."""

    @staticmethod
    def resolve_query_text(config: EmbeddingPrefixConfig, text: str) -> str:
        """Apply query prefix to text based on prefix mode."""
        if config.prefix_mode == PrefixMode.SIMPLE:
            return f"{config.query_prefix}{text}"
        elif config.prefix_mode == PrefixMode.TEMPLATE:
            return config.query_prefix.replace("{text}", text)
        else:  # API_PARAM
            return text

    @staticmethod
    def resolve_document_text(config: EmbeddingPrefixConfig, text: str) -> str:
        """Apply document prefix to text based on prefix mode."""
        if config.prefix_mode == PrefixMode.SIMPLE:
            return f"{config.document_prefix}{text}"
        elif config.prefix_mode == PrefixMode.TEMPLATE:
            if "{text}" in config.document_prefix:
                return config.document_prefix.replace("{text}", text)
            return f"{config.document_prefix}{text}"
        else:  # API_PARAM
            return text

    @staticmethod
    def get_api_params(config: EmbeddingPrefixConfig, role: str) -> dict[str, str]:
        """Return API parameters dict for the given role ('query' or 'document').

        Returns empty dict if not in api_param mode or no value configured.
        """
        if config.prefix_mode != PrefixMode.API_PARAM or not config.api_param_name:
            return {}
        if role == "query" and config.query_api_param_value:
            return {config.api_param_name: config.query_api_param_value}
        elif role == "document" and config.document_api_param_value:
            return {config.api_param_name: config.document_api_param_value}
        return {}

    @staticmethod
    def from_legacy(query_prefix: str, document_prefix: str) -> EmbeddingPrefixConfig:
        """Construct a simple-mode config from legacy flat string fields."""
        return EmbeddingPrefixConfig(
            prefix_mode=PrefixMode.SIMPLE,
            query_prefix=query_prefix,
            document_prefix=document_prefix,
        )


EMBEDDING_PREFIX_PRESETS: dict[str, EmbeddingPrefixConfig] = {
    "none": EmbeddingPrefixConfig(prefix_mode=PrefixMode.SIMPLE),
    "e5": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="query: ",
        document_prefix="passage: ",
    ),
    "e5-mistral": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ",
        document_prefix="",
    ),
    "bge": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="Represent this sentence for searching relevant passages: ",
        document_prefix="",
    ),
    "mxbai": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="Represent this sentence for searching relevant passages: ",
        document_prefix="",
    ),
    "nomic": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="search_query: ",
        document_prefix="search_document: ",
    ),
    "gte-qwen2": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ",
        document_prefix="",
    ),
    "qwen3-embedding": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ",
        document_prefix="",
    ),
    "nv-embed-v2": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="Instruct: Given a question, retrieve passages that answer the question\nQuery: ",
        document_prefix="",
    ),
    "stella": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="Instruct: Given a web search query, retrieve relevant passages that answer the query.\nQuery: ",
        document_prefix="",
    ),
    "snowflake-arctic": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.SIMPLE,
        query_prefix="query: ",
        document_prefix="",
    ),
    "cohere": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.API_PARAM,
        api_param_name="input_type",
        query_api_param_value="search_query",
        document_api_param_value="search_document",
    ),
    "jina": EmbeddingPrefixConfig(
        prefix_mode=PrefixMode.API_PARAM,
        api_param_name="task",
        query_api_param_value="retrieval.query",
        document_api_param_value="retrieval.passage",
    ),
}
