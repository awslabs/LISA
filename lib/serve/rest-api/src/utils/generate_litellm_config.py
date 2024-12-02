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

ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])
secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])


@click.command()
@click.option("-f", "--filepath", type=click.Path(exists=True, file_okay=True, dir_okay=False, writable=True))
def generate_config(filepath: str) -> None:
    """Read LiteLLM configuration and rewrite it with LISA-deployed model information."""
    with open(filepath, "r") as fp:
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
                # the following is an unused placeholder to avoid LiteLLM deployment failures
                "api_key": "ignored",  # pragma: allowlist secret
            },
        }
        for model in registered_models
    ]
    config_models = []  # ensure config_models is a list and not None
    config_models.extend(litellm_model_params)
    config_contents["model_list"] = config_models
    if "litellm_settings" not in config_contents:
        config_contents["litellm_settings"] = {
            "drop_params": True,  # drop unrecognized param instead of failing the request on it
            "request_timeout": 600,
        }
    config_contents["litellm_settings"].update(
        {
            "drop_params": True,  # drop unrecognized param instead of failing the request on it
            "request_timeout": 600,
        }
    )

    # Get database connection info
    db_param_response = ssm_client.get_parameter(Name=os.environ["LITELLM_DB_INFO_PS_NAME"])
    db_params = json.loads(db_param_response["Parameter"]["Value"])
    secrets_response = secrets_client.get_secret_value(SecretId=db_params["passwordSecretId"])
    password = json.loads(secrets_response["SecretString"])["password"]
    connection_str = (
        f"postgresql://{db_params['username']}:{password}@{db_params['dbHost']}:{db_params['dbPort']}"
        f"/{db_params['dbName']}"
    )

    config_contents["general_settings"].update(
        {
            "store_model_in_db": True,
            "database_url": connection_str,
            "master_key": config_contents["db_key"],
        }
    )

    # Write updated config back to original path
    with open(filepath, "w") as fp:
        yaml.safe_dump(config_contents, fp)


if __name__ == "__main__":
    generate_config()
