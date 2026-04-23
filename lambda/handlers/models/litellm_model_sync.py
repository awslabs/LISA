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

"""Lambda handler for syncing all models from DynamoDB to LiteLLM.

This Lambda is triggered when the LiteLLM PostgreSQL database is created or updated,
ensuring all models in the Models DynamoDB table are registered in LiteLLM.

Note: This module intentionally does NOT import from models.state_machine.create_model
to avoid requiring GUARDRAILS_TABLE_NAME at module load time.
"""

import json
import logging
import os
from typing import Any

import boto3
from lisa.domain.clients.litellm_client import LiteLLMClient
from lisa.domain.domain_objects import ModelStatus, ModelType
from lisa.utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config
from lisa.utilities.time import now

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb_resource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)
secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)


def get_litellm_client() -> LiteLLMClient:
    """Create a LiteLLM client with proper authentication."""
    return LiteLLMClient(
        base_uri=get_rest_api_container_endpoint(),
        verify=get_cert_path(iam_client),
        headers={
            "Authorization": secrets_manager.get_secret_value(
                SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT"
            )["SecretString"],
            "Content-Type": "application/json",
        },
    )


def build_litellm_params(model_item: dict[str, Any]) -> dict[str, Any]:
    """Build LiteLLM params from a DynamoDB model item."""
    model_config = model_item.get("model_config", {})
    model_name = model_config.get("modelName", "")
    model_url = model_item.get("model_url", "")
    model_type = model_config.get("modelType", "").upper()
    inference_container = model_config.get("inferenceContainer", "").lower()

    # Check if this is a video generation model
    is_video_model = model_type == ModelType.VIDEOGEN.upper()

    # For video generation models, use empty litellm_settings to avoid drop_params error
    litellm_params: dict[str, Any] = {} if is_video_model else {"drop_params": True}

    # Determine if this is a LISA-managed model (has infrastructure)
    is_lisa_managed = bool(model_url and model_config.get("autoScalingConfig"))

    if is_lisa_managed:
        # Determine the correct LiteLLM provider prefix based on the inference container type
        if inference_container == "vllm":
            provider_prefix = "hosted_vllm"
        else:
            provider_prefix = "openai"
            # Remove duplicate openai prefixing if present
            if model_name.startswith("openai/"):
                model_name = model_name[len("openai/") :]

        litellm_params["model"] = f"{provider_prefix}/{model_name}"
        litellm_params["api_base"] = model_url if model_url.endswith("/v1") else f"{model_url}/v1"
    else:
        litellm_params["model"] = model_name

    return litellm_params


def sync_model_to_litellm(
    litellm_client: LiteLLMClient, model_table: Any, model_item: dict[str, Any], existing_model_names: set[str]
) -> dict[str, Any]:
    """Sync a single model to LiteLLM.

    Args:
        litellm_client: The LiteLLM client
        model_table: The DynamoDB model table
        model_item: The model item from DynamoDB
        existing_model_names: Set of model names that already exist in LiteLLM

    Returns:
        Result dictionary with model_id and status
    """
    model_id = model_item.get("model_id", "")

    try:
        # Check if model already exists in LiteLLM by name
        if model_id in existing_model_names:
            logger.info(f"Model {model_id} already exists in LiteLLM, skipping")
            return {"model_id": model_id, "status": "skipped", "reason": "already_exists_in_litellm"}

        # Build litellm_params for this model
        litellm_params = build_litellm_params(model_item)

        # Add the model to LiteLLM
        logger.info(f"Adding model {model_id} to LiteLLM with params: {litellm_params}")
        litellm_response = litellm_client.add_model(
            model_name=model_id,
            litellm_params=litellm_params,
        )

        # Extract the LiteLLM ID from response
        if "model_info" in litellm_response and "id" in litellm_response["model_info"]:
            litellm_id = litellm_response["model_info"]["id"]
        elif "id" in litellm_response:
            litellm_id = litellm_response["id"]
        elif "model_id" in litellm_response:
            litellm_id = litellm_response["model_id"]
        else:
            logger.warning(f"Could not extract LiteLLM ID from response for model {model_id}: {litellm_response}")
            litellm_id = None

        # Update DynamoDB with the litellm_id
        if litellm_id:
            model_table.update_item(
                Key={"model_id": model_id},
                UpdateExpression="SET litellm_id = :lid, last_modified_date = :lm",
                ExpressionAttributeValues={
                    ":lid": litellm_id,
                    ":lm": now(),
                },
            )

        logger.info(f"Successfully added model {model_id} to LiteLLM with ID {litellm_id}")
        return {"model_id": model_id, "status": "synced", "litellm_id": litellm_id}

    except Exception as e:
        logger.error(f"Failed to sync model {model_id} to LiteLLM: {e}", exc_info=True)
        return {"model_id": model_id, "status": "failed", "error": str(e)}


PHYSICAL_RESOURCE_ID = "LiteLLMModelSync"


def _run_sync(force: bool = False) -> dict[str, Any]:
    """Run the model sync logic.

    Args:
        force: If True, re-sync all IN_SERVICE models regardless of existing litellm_id.

    Returns:
        Dictionary with sync summary.
    """
    model_table_name = os.environ.get("MODEL_TABLE_NAME")
    if not model_table_name:
        raise ValueError("MODEL_TABLE_NAME environment variable is not set")

    model_table = ddb_resource.Table(model_table_name)

    # Scan for all models in DynamoDB
    logger.info(f"Scanning Models table: {model_table_name}")
    models = []
    scan_kwargs: dict[str, Any] = {}

    while True:
        response = model_table.scan(**scan_kwargs)
        models.extend(response.get("Items", []))

        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    logger.info(f"Found {len(models)} models in DynamoDB")

    # Filter for models that should be synced (IN_SERVICE status)
    # In force mode, re-sync all IN_SERVICE models regardless of existing litellm_id
    eligible_models = []
    already_synced = 0
    for m in models:
        if m.get("model_status") == ModelStatus.IN_SERVICE:
            if force or not m.get("litellm_id"):
                eligible_models.append(m)
            else:
                already_synced += 1
                logger.info(f"Model {m.get('model_id')} already has litellm_id, skipping")

    logger.info(f"Found {len(eligible_models)} models needing sync, {already_synced} already synced")

    if not eligible_models:
        logger.info("No eligible models to sync")
        return {
            "message": "No eligible models to sync",
            "total_models": len(models),
            "eligible_models": 0,
            "already_synced": already_synced,
            "synced": 0,
            "skipped": 0,
            "failed": 0,
        }

    # Get existing models from LiteLLM to double-check against duplicates
    try:
        litellm_client = get_litellm_client()
        existing_litellm_models = litellm_client.list_models()
        existing_model_names: set[str] = {m.get("model_name", "") for m in existing_litellm_models}
        logger.info(f"Found {len(existing_model_names)} existing models in LiteLLM")
    except Exception as e:
        logger.warning(f"Could not list existing LiteLLM models, proceeding anyway: {e}")
        litellm_client = get_litellm_client()  # Create client anyway for syncing
        existing_model_names = set()

    # Sync each model
    results = []
    for model_item in eligible_models:
        result = sync_model_to_litellm(litellm_client, model_table, model_item, existing_model_names)
        results.append(result)

    # Summarize results
    synced = sum(1 for r in results if r["status"] == "synced")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")

    logger.info(f"Sync complete. Synced: {synced}, Skipped: {skipped}, Failed: {failed}")

    return {
        "message": "Model sync completed",
        "total_models": len(models),
        "eligible_models": len(eligible_models),
        "already_synced": already_synced,
        "synced": synced,
        "skipped": skipped,
        "failed": failed,
        "details": results,
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """CloudFormation CustomResource handler to sync models from DynamoDB to LiteLLM.

    On Create/Update: Scans the Models DynamoDB table for IN_SERVICE models and
                      registers any missing ones in LiteLLM.
    On Delete:        No-op (returns SUCCESS — nothing to clean up).

    Supports a 'force' flag via ResourceProperties to re-sync all models
    regardless of existing litellm_id.

    Args:
        event: CloudFormation CustomResource event
        context: Lambda context

    Returns:
        CustomResource response dict with PhysicalResourceId, Status, and Data.
    """
    request_type = event.get("RequestType", "")
    logger.info(f"LiteLLM model sync invoked: RequestType={request_type}")

    # Delete is a no-op — nothing to clean up.
    # IMPORTANT: Return the *incoming* PhysicalResourceId on Delete so the CDK
    # framework doesn't reject the response for changing the physical ID.
    if request_type == "Delete":
        logger.info("RequestType=Delete: no-op, returning SUCCESS")
        physical_id = event.get("PhysicalResourceId", PHYSICAL_RESOURCE_ID)
        return {"Status": "SUCCESS", "PhysicalResourceId": physical_id}

    # Create and Update both run the sync
    try:
        # Check for force flag in ResourceProperties
        resource_props = event.get("ResourceProperties", {}) or {}
        force = bool(resource_props.get("force", False))
        logger.info(f"Starting LiteLLM model sync. Event: {json.dumps(event)}, force={force}")

        data = _run_sync(force=force)
        return {
            "Status": "SUCCESS",
            "PhysicalResourceId": PHYSICAL_RESOURCE_ID,
            "Data": data,
        }
    except Exception as e:
        logger.error(f"LiteLLM model sync failed: {e}", exc_info=True)
        return {
            "Status": "FAILED",
            "PhysicalResourceId": PHYSICAL_RESOURCE_ID,
            "Reason": str(e),
        }
