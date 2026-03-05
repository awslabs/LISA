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

"""Handler for bulk retroactive context window enrichment."""

import json
import logging
import os

import boto3
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config
from utilities.time import now

from ..clients.litellm_client import LiteLLMClient
from ..domain_objects import BulkEnrichContextWindowResponse, ModelType
from .base_handler import BaseApiHandler

logger = logging.getLogger(__name__)

s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)


def _get_litellm_client() -> LiteLLMClient:
    """Build a LiteLLMClient from the Lambda environment at call-time."""
    iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)
    secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
    secret = secrets_manager.get_secret_value(
        SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT"
    )["SecretString"]
    return LiteLLMClient(
        base_uri=get_rest_api_container_endpoint(),
        verify=get_cert_path(iam_client),
        headers={
            "Authorization": secret,
            "Content-Type": "application/json",
        },
    )


def _fetch_from_litellm(litellm_client: LiteLLMClient, litellm_id: str | None, model_id: str) -> int | None:
    """Return max_input_tokens from LiteLLM for a non-LISA-managed model.

    Falls back to list_models() filtered by model_id when litellm_id is absent
    (pre-existing records created before litellm_id was stored).
    """
    if litellm_id:
        try:
            model_info = litellm_client.get_model(litellm_id)
            return int(model_info.get("model_info", {}).get("max_input_tokens"))
        except Exception as e:
            logger.warning(f"get_model failed for litellm_id={litellm_id}: {e}")

    # Fallback: scan all models in LiteLLM and match by model_name == model_id
    try:
        all_models = litellm_client.list_models()
        matches = [m for m in all_models if m.get("model_name") == model_id]
        if matches:
            return int(matches[0].get("model_info", {}).get("max_input_tokens"))
    except Exception as e:
        logger.warning(f"list_models fallback failed for model_id={model_id}: {e}")

    return None


def _fetch_from_s3(bucket: str, model_name: str, model_type: str) -> int | None:
    """Return max_position_embeddings from the model's config.json in S3."""
    paths = [f"{model_name}/config.json"]
    if model_type.upper() == ModelType.IMAGEGEN.upper():
        paths.append(f"{model_name}/text_encoder/config.json")

    for path in paths:
        try:
            obj = s3_client.get_object(Bucket=bucket, Key=path)
            config = json.loads(obj["Body"].read())
            val = config.get("max_position_embeddings")
            if val is not None:
                return int(val)
        except s3_client.exceptions.NoSuchKey:
            continue
        except Exception as e:
            logger.warning(f"Could not read s3://{bucket}/{path}: {e}")

    return None


def _is_lisa_managed(model_item: dict) -> bool:
    """Determine if a model is LISA-managed (has self-hosted ECS infrastructure)."""
    model_config = model_item.get("model_config", {})
    return all(
        bool(model_config.get(field))
        for field in (
            "autoScalingConfig",
            "containerConfig",
            "inferenceContainer",
            "instanceType",
            "loadBalancerConfig",
        )
    )


class BulkEnrichContextWindowHandler(BaseApiHandler):
    """Retroactively enrich all DDB model records that are missing a context_window value."""

    def __call__(self) -> BulkEnrichContextWindowResponse:
        """Scan the model table and attempt context window enrichment for each model lacking it."""
        enriched: list[str] = []
        skipped: list[str] = []
        failed: dict[str, str] = {}

        bucket = os.environ.get("MODELS_BUCKET_NAME", "")
        litellm_client = _get_litellm_client()

        # Full scan with pagination
        all_items: list[dict] = []
        scan_kwargs: dict = {}
        while True:
            response = self._model_table.scan(**scan_kwargs)
            all_items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        for item in all_items:
            model_id = item.get("model_id", "")
            if not model_id:
                continue

            # Skip models that already have a context window
            if item.get("context_window") is not None:
                skipped.append(model_id)
                continue

            context_window: int | None = None
            try:
                if _is_lisa_managed(item) and bucket:
                    model_name = item.get("model_config", {}).get("modelName", "")
                    model_type = item.get("model_config", {}).get("modelType", "")
                    context_window = _fetch_from_s3(bucket, model_name, model_type)
                else:
                    litellm_id = item.get("litellm_id")
                    context_window = _fetch_from_litellm(litellm_client, litellm_id, model_id)

                if context_window is not None:
                    self._model_table.update_item(
                        Key={"model_id": model_id},
                        UpdateExpression="SET context_window = :cw, last_modified_date = :lm",
                        ExpressionAttributeValues={":cw": context_window, ":lm": now()},
                    )
                    enriched.append(model_id)
                    logger.info(f"Bulk enriched model {model_id} with context_window={context_window}")
                else:
                    failed[model_id] = "Could not determine context window from LiteLLM or S3"
                    logger.warning(f"Could not determine context window for model {model_id}")

            except Exception as e:
                error_msg = str(e)
                failed[model_id] = error_msg
                logger.error(f"Error enriching context window for model {model_id}: {error_msg}", exc_info=True)

        return BulkEnrichContextWindowResponse(enriched=enriched, skipped=skipped, failed=failed)
