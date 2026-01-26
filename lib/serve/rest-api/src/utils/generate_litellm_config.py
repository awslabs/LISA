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

"""Generates the LiteLLM config from customer-provided config and hosted model endpoints."""

import json
import os

import boto3
import click
import yaml


@click.command()
@click.option("-f", "--filepath", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=True))
def generate_config(filepath: str) -> None:
    """Read LiteLLM configuration and rewrite it with LISA-deployed model information."""
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])

    with open(filepath) as fp:
        config_contents = yaml.safe_load(fp)
    # Get and load registered models from ParameterStore
    param_response = ssm_client.get_parameter(Name=os.environ["REGISTERED_MODELS_PS_NAME"])
    registered_models = json.loads(param_response["Parameter"]["Value"])
    # Generate model definitions for each of the LISA-deployed models
    litellm_model_params = [
        {
            "model_name": model["modelId"],  # Use user-provided name if one given, otherwise it is the model name.
            "litellm_params": {
                "model": f"openai/{model['modelName']}",
                "api_base": model["endpointUrl"] + "/v1",  # Local containers require the /v1 for OpenAI API routing.
            },
        }
        for model in registered_models
    ]
    config_models = []  # ensure config_models is a list and not None
    config_models.extend(litellm_model_params)
    config_contents["model_list"] = config_models
    if "litellm_settings" not in config_contents:
        config_contents["litellm_settings"] = {}
    config_contents["litellm_settings"].update(
        {
            "drop_params": True,  # drop unrecognized param instead of failing the request on it
            "request_timeout": 600,
        }
    )

    # Get database connection info
    db_param_response = ssm_client.get_parameter(Name=os.environ["LITELLM_DB_INFO_PS_NAME"])
    db_params = json.loads(db_param_response["Parameter"]["Value"])

    # Check if using IAM auth - either via environment variable (preferred) or SSM parameter
    # IAM_TOKEN_DB_AUTH is set by CDK when iamRdsAuth=true
    use_iam_auth = os.environ.get("IAM_TOKEN_DB_AUTH", "").lower() == "true" or "passwordSecretId" not in db_params

    if "general_settings" not in config_contents:
        config_contents["general_settings"] = {}

    if use_iam_auth:
        # For IAM auth, LiteLLM uses DATABASE_* environment variables set by CDK
        # LiteLLM automatically generates and refreshes IAM auth tokens when IAM_TOKEN_DB_AUTH=true
        # We do NOT set database_url in the config - LiteLLM builds it from env vars
        print("IAM auth enabled via environment variables")
        print(f"  DATABASE_HOST: {os.environ.get('DATABASE_HOST', 'not set')}")
        print(f"  DATABASE_NAME: {os.environ.get('DATABASE_NAME', 'not set')}")
        print(f"  DATABASE_PORT: {os.environ.get('DATABASE_PORT', 'not set')}")
        print(f"  DATABASE_USER: {os.environ.get('DATABASE_USER', 'not set')}")

        config_contents["general_settings"].update(
            {
                "store_model_in_db": True,
                "master_key": config_contents["db_key"],
            }
        )
    else:
        # Password auth: build connection string with password from Secrets Manager
        username, password = get_database_credentials(db_params)
        connection_str = (
            f"postgresql://{username}:{password}@{db_params['dbHost']}:{db_params['dbPort']}" f"/{db_params['dbName']}"
        )

        config_contents["general_settings"].update(
            {
                "store_model_in_db": True,
                "database_url": connection_str,
                "master_key": config_contents["db_key"],
            }
        )

    print(f"Generated config_contents file: \n{json.dumps(config_contents, indent=2)}")

    # Write updated config back to original path
    with open(filepath, "w") as fp:
        yaml.safe_dump(config_contents, fp)


def get_database_credentials(db_params: dict[str, str]) -> tuple:
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


if __name__ == "__main__":
    generate_config()
