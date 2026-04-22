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

"""Context Window Backfill Lambda.

This Lambda function retroactively enriches existing model DynamoDB records
with a context_window value. It runs once automatically during CDK deployment
via a CloudFormation CustomResource.

On Create:  Scans all model records and populates context_window where missing.
On Update:  No-op (returns SUCCESS immediately — the static PhysicalResourceId
            prevents CloudFormation from triggering Update unless properties change).
On Delete:  No-op (returns SUCCESS — nothing to clean up).

Lookup strategy per model type:
  - LISA-managed models (self-hosted ECS):  reads max_position_embeddings from
    the model's config.json in the S3 models bucket. For IMAGEGEN models, also
    tries text_encoder/config.json as a fallback.
  - External / Bedrock models:              queries LiteLLM's /model/info endpoint
    using the stored litellm_id. Falls back to scanning all LiteLLM models by
    model_name when litellm_id is absent (pre-6.x records).

If a value cannot be determined, context_window is set to 0.
"""

import json
import logging
import os
import traceback
from typing import Any

import boto3
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import ModelType
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config
from utilities.time import now

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Static physical resource ID — never changes, so CloudFormation only runs this once.
PHYSICAL_RESOURCE_ID = "context-window-backfill"


# ============================================================================
# Helpers
# ============================================================================


def _get_litellm_client() -> LiteLLMClient:
    """Build a LiteLLMClient from the Lambda environment at call-time."""
    iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)
    secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
    secret = secrets_manager.get_secret_value(SecretId=os.environ["MANAGEMENT_KEY_NAME"], VersionStage="AWSCURRENT")[
        "SecretString"
    ]
    return LiteLLMClient(
        base_uri=get_rest_api_container_endpoint(),
        verify=get_cert_path(iam_client),
        headers={
            "Authorization": secret,
            "Content-Type": "application/json",
        },
    )


def _fetch_context_window_from_litellm(
    litellm_client: LiteLLMClient, litellm_id: str | None, model_id: str
) -> int | None:
    """Return max_input_tokens from LiteLLM for a non-LISA-managed model.

    Falls back to list_models() filtered by model_id when litellm_id is absent (pre-existing records created before
    litellm_id was stored).
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


def _fetch_context_window_from_s3(s3_client: Any, bucket: str, model_name: str, model_type: str) -> int | None:
    """Return max_position_embeddings from the model's config.json in S3.

    For IMAGEGEN models, also checks text_encoder/config.json as a fallback.
    """
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
    """Return True if the model has self-hosted ECS infrastructure."""
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


# ============================================================================
# Backfill logic
# ============================================================================


def _run_backfill() -> dict[str, Any]:
    """Scan the model table and enrich all records missing context_window."""
    model_table_name = os.environ["MODEL_TABLE_NAME"]
    bucket = os.environ.get("MODELS_BUCKET_NAME", "")

    dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
    s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
    model_table = dynamodb.Table(model_table_name)

    litellm_client = _get_litellm_client()

    # Full DynamoDB scan with pagination
    all_items: list[dict] = []
    scan_kwargs: dict = {}
    while True:
        response = model_table.scan(**scan_kwargs)
        all_items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    enriched = 0
    skipped = 0
    failed = 0

    for item in all_items:
        model_id = item.get("model_id", "")
        if not model_id:
            continue

        # Skip models that already have a context window
        if item.get("context_window") is not None:
            skipped += 1
            continue

        context_window: int | None = None
        try:
            if _is_lisa_managed(item) and bucket:
                # Self-hosted model — read context window from the model's S3 config.json
                model_name = item.get("model_config", {}).get("modelName", "")
                model_type = item.get("model_config", {}).get("modelType", "")
                context_window = _fetch_context_window_from_s3(s3_client, bucket, model_name, model_type)
            else:
                # External / Bedrock model — query LiteLLM for max_input_tokens
                litellm_id = item.get("litellm_id")
                context_window = _fetch_context_window_from_litellm(litellm_client, litellm_id, model_id)

            if context_window is None:
                logger.warning(f"Could not determine context window for {model_id}, defaulting to 0")
                context_window = 0

            model_table.update_item(
                Key={"model_id": model_id},
                UpdateExpression="SET context_window = :cw, last_modified_date = :lm",
                ExpressionAttributeValues={":cw": context_window, ":lm": now()},
            )
            enriched += 1
            logger.info(f"Backfilled model {model_id} with context_window={context_window}")

        except Exception as e:
            failed += 1
            logger.error(f"Error backfilling model {model_id}: {e}", exc_info=True)

    summary = f"context_window backfill complete: enriched={enriched}, skipped={skipped}, failed={failed}"
    logger.info(summary)
    return {"enriched": str(enriched), "skipped": str(skipped), "failed": str(failed)}


# ============================================================================
# Lambda handler
# ============================================================================


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """CloudFormation CustomResource handler for context window backfill.

    Runs the backfill exactly once on Create. Update and Delete are no-ops. The static PhysicalResourceId ensures
    CloudFormation never re-creates or replaces this resource across subsequent deployments.
    """
    request_type = event.get("RequestType", "")
    logger.info(f"context-window-backfill invoked: RequestType={request_type}")

    # Update and Delete are no-ops — the backfill only ever needs to run once
    if request_type in ("Update", "Delete"):
        logger.info(f"RequestType={request_type}: no-op, returning SUCCESS")
        return {"Status": "SUCCESS", "PhysicalResourceId": PHYSICAL_RESOURCE_ID}

    # Create: run the backfill
    try:
        data = _run_backfill()
        return {
            "Status": "SUCCESS",
            "PhysicalResourceId": PHYSICAL_RESOURCE_ID,
            "Data": data,
        }
    except Exception as e:
        logger.error(f"context-window backfill failed: {e}")
        logger.error(traceback.format_exc())
        return {
            "Status": "FAILED",
            "PhysicalResourceId": PHYSICAL_RESOURCE_ID,
            "Reason": str(e),
        }
