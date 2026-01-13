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
from typing import Any, List

import boto3
import requests
from pydantic import BaseModel, ConfigDict, field_validator
from utilities.auth import get_management_key
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config
from utilities.validation import validate_model_name, ValidationError

logger = logging.getLogger(__name__)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)

lisa_api_endpoint = ""


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

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        validate_model_name(v)
        return v

    def __init__(self, model_name: str, id_token: str | None = None, **data: Any) -> None:
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
            logger.info("Successfully initialized pipeline embeddings")
        except Exception:
            logger.error("Failed to initialize pipeline embeddings", exc_info=True)
            raise

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ValidationError: If input texts are invalid
            Exception: If embedding request fails
        """
        if not texts:
            raise ValidationError("No texts provided for embedding")

        logger.info(f"Embedding {len(texts)} documents using {self.model_name}")
        try:
            url = f"{self.base_url}/embeddings"
            request_data = {"input": texts, "model": self.model_name}
            response = requests.post(
                url,
                json=request_data,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                verify=self.cert_path,  # Use proper SSL verification
                timeout=300,  # 5 minute timeout
            )

            if response.status_code != 200:
                logger.error(f"Embedding request failed with status {response.status_code}")
                raise Exception(f"Embedding request failed with status {response.status_code}")

            result = response.json()
            logger.debug(f"API Response: {result}")  # Log the full response for debugging

            # Handle different response formats
            embeddings = []
            if isinstance(result, dict):
                if "data" in result:
                    # OpenAI-style format
                    for item in result["data"]:
                        if isinstance(item, dict) and "embedding" in item:
                            embeddings.append(item["embedding"])
                        else:
                            embeddings.append(item)  # Assume the item itself is the embedding
                else:
                    # Try to find embeddings in the response
                    for key in ["embeddings", "embedding", "vectors", "vector"]:
                        if key in result:
                            embeddings = result[key]
                            break
            elif isinstance(result, list):
                # Direct list format
                embeddings = result

            if not embeddings:
                logger.error(f"Could not find embeddings in response: {result}")
                raise Exception("No embeddings found in API response")

            if len(embeddings) != len(texts):
                logger.error(f"Mismatch between number of texts ({len(texts)}) and embeddings ({len(embeddings)})")
                raise Exception("Number of embeddings does not match number of input texts")

            logger.info(f"Successfully embedded {len(texts)} documents")
            return embeddings

        except requests.Timeout:
            logger.error("Embedding request timed out")
            raise Exception("Embedding request timed out after 5 minutes")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to get embeddings: {str(e)}", exc_info=True)
            raise

    def embed_query(self, text: str) -> List[float]:
        if not text or not isinstance(text, str):
            raise ValidationError("Invalid query text")

        logger.info("Embedding single query text")
        return self.embed_documents([text])[0]
