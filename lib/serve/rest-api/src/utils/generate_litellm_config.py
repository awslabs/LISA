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

"""Generates the LiteLLM config with DB connection info and production settings.

Models are managed dynamically via LiteLLM's DB (store_model_in_db=True).

Uses LiteLLM's ConfigYAML pydantic model for top-level structure validation.
Note: general_settings is kept as a dict because LiteLLM's ConfigGeneralSettings
model does not include all runtime-accepted fields (e.g., proxy_batch_write_at,
disable_error_logs, allow_requests_on_db_unavailable). These fields are consumed
by LiteLLM at runtime via dict access but are not in the pydantic schema.
"""

import json
import os
from typing import Any

import boto3
import click
import yaml
from litellm.proxy._types import ConfigYAML

# Fields that must be redacted from log output
_SENSITIVE_FIELDS = {"database_url", "master_key"}
_SENSITIVE_TOP_LEVEL = {"db_key"}


def _build_litellm_settings() -> dict[str, Any]:
    """Build the litellm_settings section of the config."""
    return {
        "drop_params": True,
        "request_timeout": 600,
        "set_verbose": os.environ.get("DEBUG", "").lower() == "true",
        "num_retries": 2,
        "retry_after": 1,
        "embedding_cache": True,
    }


def _build_general_settings(db_key: str, db_params: dict[str, str], use_iam_auth: bool) -> dict[str, Any]:
    """Build the general_settings section with production best practices.

    See: https://docs.litellm.ai/docs/proxy/prod
    """
    settings: dict[str, Any] = {
        "proxy_batch_write_at": 60,
        "database_connection_pool_limit": 10,
        "disable_error_logs": True,
        "allow_requests_on_db_unavailable": True,
        "store_model_in_db": True,
        "master_key": db_key,
    }

    if not use_iam_auth:
        username, password = _get_database_credentials(db_params)
        settings["database_url"] = (
            f"postgresql://{username}:{password}" f"@{db_params['dbHost']}:{db_params['dbPort']}/{db_params['dbName']}"
        )

    return settings


def _get_database_credentials(db_params: dict[str, str]) -> tuple[str, str]:
    """Get database credentials using password auth from Secrets Manager."""
    secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    try:
        secret_response = secrets_client.get_secret_value(SecretId=db_params["passwordSecretId"])
    except secrets_client.exceptions.ResourceNotFoundException:
        raise RuntimeError(
            f"Database password secret '{db_params['passwordSecretId']}' not found. "
            "This typically occurs when switching from IAM authentication (iamRdsAuth=true) "
            "back to password authentication (iamRdsAuth=false). The master password is "
            "permanently deleted when IAM auth is enabled. To resolve this, either: "
            "1) Set iamRdsAuth=true in your config, or "
            "2) Recreate the database by deleting and redeploying the stack."
        )
    secret = json.loads(secret_response["SecretString"])
    return (db_params["username"], secret["password"])


def _redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """Create a copy of config with sensitive fields redacted for logging."""
    safe: dict[str, Any] = json.loads(json.dumps(config))
    for key in _SENSITIVE_TOP_LEVEL:
        if key in safe:
            safe[key] = "***REDACTED***"
    gs = safe.get("general_settings", {})
    for key in _SENSITIVE_FIELDS:
        if key in gs:
            gs[key] = "***REDACTED***"
    return safe


@click.command()
@click.option("-f", "--filepath", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=True))
def generate_config(filepath: str) -> None:
    """Read LiteLLM configuration and rewrite it with DB connection and production settings."""
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])

    with open(filepath) as fp:
        config_contents: dict[str, Any] = yaml.safe_load(fp) or {}

    # Build litellm_settings, merging with any customer-provided values
    existing_litellm_settings = config_contents.get("litellm_settings", {}) or {}
    existing_litellm_settings.update(_build_litellm_settings())
    config_contents["litellm_settings"] = existing_litellm_settings

    # Get database connection info from SSM
    db_param_response = ssm_client.get_parameter(Name=os.environ["LITELLM_DB_INFO_PS_NAME"])
    db_params: dict[str, str] = json.loads(db_param_response["Parameter"]["Value"])

    # Determine auth method
    use_iam_auth = os.environ.get("IAM_TOKEN_DB_AUTH", "").lower() == "true" or "passwordSecretId" not in db_params

    # Build general_settings, merging with any customer-provided values
    existing_general_settings = config_contents.get("general_settings", {}) or {}
    existing_general_settings.update(_build_general_settings(config_contents["db_key"], db_params, use_iam_auth))
    config_contents["general_settings"] = existing_general_settings

    # Validate top-level structure using LiteLLM's pydantic model.
    # ConfigYAML validates model_list, litellm_settings (dict), general_settings
    # (ConfigGeneralSettings), and router_settings. Extra fields like db_key are
    # preserved in the raw dict but not validated by the model.
    try:
        ConfigYAML(**{k: v for k, v in config_contents.items() if k in ConfigYAML.model_fields})
        print("Config validation passed")
    except Exception as e:
        print(f"Config validation warning: {e}")

    print(f"Generated config:\n{json.dumps(_redact_config(config_contents), indent=2)}")

    with open(filepath, "w") as fp:
        yaml.safe_dump(config_contents, fp)


if __name__ == "__main__":
    generate_config()
