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

import logging
import os
import time
from typing import Any

import boto3
import requests
from models.domain_objects import EmbeddingPrefixConfig
from pydantic import BaseModel, ConfigDict, field_validator
from repository.prefix_resolver import PrefixResolver
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utilities.auth import get_management_key
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config
from utilities.validation import validate_model_name, ValidationError

logger = logging.getLogger(__name__)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)

lisa_api_endpoint = ""

# Max texts per embedding API call — TEI containers enforce a 256 limit
MAX_EMBEDDING_BATCH_SIZE = 256
# Retry configuration for transient embedding failures
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


def get_model_embedding_prefixes(model_name: str) -> EmbeddingPrefixConfig:
    """Look up embedding prefix configuration from the models DynamoDB table.

    Args:
        model_name: The model ID to look up.

    Returns:
        EmbeddingPrefixConfig with the model's prefix settings, or a default empty config.
    """
    table_name = os.environ.get("MODEL_TABLE_NAME")
    if not table_name:
        logger.debug("MODEL_TABLE_NAME not set, skipping prefix lookup")
        return EmbeddingPrefixConfig()

    try:
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"model_id": model_name})
        item = response.get("Item")
        if not item:
            logger.debug(f"Model {model_name} not found in model table")
            return EmbeddingPrefixConfig()

        model_config = item.get("model_config", {})

        # Try structured config first
        prefix_config_data = model_config.get("embeddingPrefixConfig")
        if prefix_config_data:
            try:
                return EmbeddingPrefixConfig.model_validate(prefix_config_data)
            except Exception:
                logger.warning(
                    f"Invalid embeddingPrefixConfig for {model_name}, falling back to legacy fields",
                    exc_info=True,
                )

        # Fall back to legacy flat fields
        query_prefix = model_config.get("embeddingQueryPrefix") or ""
        document_prefix = model_config.get("embeddingDocumentPrefix") or ""
        if query_prefix or document_prefix:
            return PrefixResolver.from_legacy(query_prefix, document_prefix)

        return EmbeddingPrefixConfig()
    except Exception:
        logger.warning(f"Failed to look up model prefixes for {model_name}", exc_info=True)
        return EmbeddingPrefixConfig()


# Module-level session with connection pooling for better performance
# This reuses TCP connections across multiple embedding requests
_http_session: requests.Session | None = None


def _get_http_session() -> requests.Session:
    """Get or create a shared HTTP session with connection pooling."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        # Configure retry strategy for transient failures
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
        )
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,  # Max connections per pool
            max_retries=retry_strategy,
        )
        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)
    return _http_session


class RagEmbeddings(BaseModel):
    """
    Handles document embeddings through LiteLLM using management credentials.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str
    token: str
    lisa_api_endpoint: str
    base_url: str
    cert_path: str | bool
    prefix_config: EmbeddingPrefixConfig = EmbeddingPrefixConfig()

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        validate_model_name(v)
        return v

    def __init__(self, model_name: str, id_token: str | None = None, **data: Any) -> None:
        # Handle backward compatibility: convert legacy query_prefix/document_prefix kwargs
        query_prefix = data.pop("query_prefix", None)
        document_prefix = data.pop("document_prefix", None)
        if (query_prefix is not None or document_prefix is not None) and "prefix_config" not in data:
            data["prefix_config"] = PrefixResolver.from_legacy(
                query_prefix or "",
                document_prefix or "",
            )

        # Prepare initialization data
        init_data = {"model_name": model_name, **data}
        try:
            # Use management token if id_token is not provided
            if id_token is None:
                logger.info("Using management key for ingestion")
                init_data["token"] = get_management_key()
            else:
                init_data["token"] = id_token

            init_data["lisa_api_endpoint"] = get_rest_api_container_endpoint()
            init_data["base_url"] = get_rest_api_container_endpoint()
            init_data["cert_path"] = get_cert_path(iam_client)

            super().__init__(**init_data)
            logger.info(
                f"Successfully initialized pipeline embeddings "
                f"(prefix_config={self.prefix_config!r})"
            )
        except Exception:
            logger.error("Failed to initialize pipeline embeddings", exc_info=True)
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of documents, automatically batching
        to stay within the embedding server's max batch size.

        Applies document prefix via PrefixResolver and passes API params if configured.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ValidationError: If input texts are invalid
            Exception: If embedding request fails after retries
        """
        if not texts:
            raise ValidationError("No texts provided for embedding")

        # Apply document prefix via PrefixResolver
        texts = [PrefixResolver.resolve_document_text(self.prefix_config, t) for t in texts]
        api_params = PrefixResolver.get_api_params(self.prefix_config, "document")

        logger.info(f"Embedding {len(texts)} documents using {self.model_name}")

        all_embeddings: list[list[float]] = []
        batch_size = MAX_EMBEDDING_BATCH_SIZE

        for batch_start in range(0, len(texts), batch_size):
            batch = texts[batch_start : batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(texts) + batch_size - 1) // batch_size
            logger.info(f"Embedding batch {batch_num}/{total_batches} ({len(batch)} texts)")

            batch_embeddings = self._embed_batch_with_retry(batch, extra_params=api_params)
            all_embeddings.extend(batch_embeddings)

        if len(all_embeddings) != len(texts):
            raise Exception(f"Embedding count mismatch: expected {len(texts)}, got {len(all_embeddings)}")

        logger.info(f"Successfully embedded {len(texts)} documents")
        return all_embeddings

    def _embed_batch_with_retry(
        self, texts: list[str], extra_params: dict[str, str] | None = None
    ) -> list[list[float]]:
        """Send a single batch to the embedding API with exponential backoff on failure."""
        last_exception: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._call_embedding_api(texts, extra_params=extra_params)
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        f"Embedding attempt {attempt}/{MAX_RETRIES} failed: {e}. " f"Retrying in {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Embedding failed after {MAX_RETRIES} attempts: {e}")

        raise last_exception  # type: ignore[misc]

    def _call_embedding_api(self, texts: list[str], extra_params: dict[str, str] | None = None) -> list[list[float]]:
        """Make a single embedding HTTP request and parse the response."""
        url = f"{self.base_url}/embeddings"
        request_data: dict[str, Any] = {
            "input": texts,
            "model": self.model_name,
            "encoding_format": "float",
        }
        if extra_params:
            request_data.update(extra_params)

        session = _get_http_session()
        try:
            response = session.post(
                url,
                json=request_data,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                verify=self.cert_path,
                timeout=300,
            )
        except requests.Timeout:
            raise Exception("Embedding request timed out after 5 minutes")
        except requests.RequestException as e:
            raise Exception(f"Embedding HTTP request failed: {e}") from e

        if response.status_code != 200:
            logger.error(f"Embedding request failed with status {response.status_code}: {response.text}")
            raise Exception(f"Embedding request failed with status {response.status_code}")

        result = response.json()
        return self._parse_embeddings(result, expected_count=len(texts))

    @staticmethod
    def _parse_embeddings(result: Any, expected_count: int) -> list[list[float]]:
        """Extract embedding vectors from the API response."""
        embeddings: list[list[float]] = []

        if isinstance(result, dict):
            if "data" in result:
                # OpenAI-style format
                for item in result["data"]:
                    if isinstance(item, dict) and "embedding" in item:
                        embeddings.append(item["embedding"])
                    else:
                        embeddings.append(item)
            else:
                for key in ["embeddings", "embedding", "vectors", "vector"]:
                    if key in result:
                        embeddings = result[key]
                        break
        elif isinstance(result, list):
            embeddings = result

        if not embeddings:
            logger.error(f"Could not find embeddings in response: {result}")
            raise Exception("No embeddings found in API response")

        if len(embeddings) != expected_count:
            raise Exception(f"Embedding count mismatch: expected {expected_count}, got {len(embeddings)}")

        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text, applying query prefix via PrefixResolver.

        Applies query prefix to text based on prefix mode and passes API params if configured.

        Args:
            text: Query text string to embed

        Returns:
            Embedding vector for the query

        Raises:
            ValidationError: If input text is invalid
            Exception: If embedding request fails after retries
        """
        if not text or not isinstance(text, str):
            raise ValidationError("Invalid query text")

        # Apply query prefix via PrefixResolver
        text = PrefixResolver.resolve_query_text(self.prefix_config, text)
        api_params = PrefixResolver.get_api_params(self.prefix_config, "query")

        logger.info("Embedding single query text")
        result = self._embed_batch_with_retry([text], extra_params=api_params)
        return result[0]
