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

"""
Model API Key Cleanup Lambda

This Lambda function removes the api_key field from existing Bedrock models
that were created with the old LiteLLM version that required api_key = "ignored".  # pragma: allowlist secret
This fixes "Invalid API Key format" errors for Bedrock models that don't need API keys.

Only models with modelName prefixed with "bedrock/" are processed.

The cleanup runs automatically during CDK deployment via a CustomResource.
"""

import json
import os
import sys
import traceback
from typing import Any

import boto3
import psycopg2
from utilities.common_functions import get_lambda_role_name, retry_config
from utilities.rds_auth import generate_auth_token

# Add the lambda directory to the Python path
sys.path.append("/opt/python")
sys.path.append("/var/task")


def get_all_dynamodb_models() -> list[dict[str, str]]:
    """Get all models from DynamoDB table with their IDs and names."""
    try:
        dynamodb = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)

        # Get model table name from SSM parameter
        deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX")
        if not deployment_prefix:
            raise ValueError("DEPLOYMENT_PREFIX environment variable not set")
        model_table_param = f"{deployment_prefix}/modelTableName"

        try:
            table_name_response = ssm_client.get_parameter(Name=model_table_param)
            table_name = table_name_response["Parameter"]["Value"]

            if not table_name:
                raise ValueError("Empty table name returned from SSM")

        except Exception as e:
            print(f"Could not get model table name from SSM: {e}")
            return []

        # Scan the entire DynamoDB table to get all models
        response = dynamodb.scan(TableName=table_name)

        models = []
        for item in response.get("Items", []):
            # Extract model_id and modelName from the item with proper validation
            model_id = item.get("model_id", {}).get("S", "")
            model_config = item.get("model_config", {})
            model_name = ""

            if "M" in model_config and "modelName" in model_config["M"]:
                model_name = model_config["M"]["modelName"].get("S", "")

            # Only include models with both ID and name
            if model_id and model_name:
                models.append({"model_id": model_id, "model_name": model_name})

        print(f"Found {len(models)} models in DynamoDB")
        return models

    except Exception as e:
        print(f"Error scanning DynamoDB table: {e}")
        return []


def get_database_connection() -> Any:
    """Get database connection using password auth or IAM auth based on config."""
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)

    # Get database connection info from SSM using environment variable
    deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX")
    if not deployment_prefix:
        raise ValueError("DEPLOYMENT_PREFIX environment variable not set")
    db_param_name = f"{deployment_prefix}/LiteLLMDbConnectionInfo"

    try:
        db_param_response = ssm_client.get_parameter(Name=db_param_name, WithDecryption=True)
        db_params = json.loads(db_param_response["Parameter"]["Value"])
    except Exception as e:
        raise ValueError(f"Failed to get database connection info from SSM: {e}")

    # Validate required parameters
    required_params = ["dbHost", "dbPort", "dbName"]
    for param in required_params:
        if param not in db_params:
            raise ValueError(f"Missing required database parameter: {param}")

    # Check if using password auth (passwordSecretId present) or IAM auth
    if "passwordSecretId" in db_params:
        # Password auth: get credentials from Secrets Manager
        try:
            secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
            secret_response = secrets_client.get_secret_value(SecretId=db_params["passwordSecretId"])
            secret = json.loads(secret_response["SecretString"])
        except Exception as e:
            raise ValueError(f"Failed to get database credentials from Secrets Manager: {e}")

        if "password" not in secret:
            raise ValueError("Missing password in secret")

        user = db_params.get("username", "postgres")
        password = secret["password"]
    else:
        # IAM auth: generate auth token
        user = get_lambda_role_name()
        password = generate_auth_token(db_params["dbHost"], db_params["dbPort"], user)

    # Create connection
    try:
        conn = psycopg2.connect(
            host=db_params["dbHost"],
            port=db_params["dbPort"],
            database=db_params["dbName"],
            user=user,
            password=password,
        )
        return conn
    except Exception as e:
        raise ValueError(f"Failed to connect to database: {e}")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for Bedrock model API key cleanup.

    Only processes models with modelName prefixed with "bedrock/".

    Args:
        event: CloudFormation CustomResource event
        context: Lambda context

    Returns:
        CloudFormation CustomResource response
    """
    print("Starting Bedrock model API key cleanup...")

    # Validate environment variables
    required_env_vars = ["AWS_REGION", "DEPLOYMENT_PREFIX"]
    for env_var in required_env_vars:
        if not os.environ.get(env_var):
            error_msg = f"Missing required environment variable: {env_var}"
            print(error_msg)
            return {"Status": "FAILED", "PhysicalResourceId": "bedrock-auth-cleanup", "Reason": error_msg}

    conn = None
    cursor = None

    try:
        # Get database connection
        conn = get_database_connection()
        cursor = conn.cursor()

        # First, let's see what tables exist in the database
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = cursor.fetchall()
        print(f"Available tables in database: {[table[0] for table in tables]}")

        # Try to find the correct LiteLLM model table name
        litellm_table = None
        for table in tables:
            table_name = table[0]
            if "proxymodel" in table_name.lower() or table_name == "LiteLLM_ProxyModelTable":
                litellm_table = table_name
                print(f"Found LiteLLM model table: {table_name}")
                break

        if not litellm_table:
            print("No LiteLLM model table found in database. Database might not be initialized yet.")
            print("Bedrock model cleanup completed! 0 Bedrock models updated (no LiteLLM tables found)")
            # Return success response for CloudFormation CustomResource
            return {"Status": "SUCCESS", "PhysicalResourceId": "bedrock-auth-cleanup", "Data": {"ModelsUpdated": "0"}}

        # Query all models from the LiteLLM database using the found table (use quotes for case-sensitive names)

        # Use psycopg2's identifier quoting to prevent SQL injection
        cursor.execute(
            psycopg2.sql.SQL("SELECT * FROM {} LIMIT 1").format(psycopg2.sql.Identifier(litellm_table))  # noqa: S608
        )
        columns = [desc[0] for desc in cursor.description]
        print(f"Table {litellm_table} columns: {columns}")

        # Try to find the correct column names
        model_id_col = next((col for col in columns if "id" in col.lower()), None)
        model_name_col = next((col for col in columns if "name" in col.lower()), None)
        litellm_params_col = next((col for col in columns if "param" in col.lower()), None)

        if not all([model_id_col, model_name_col, litellm_params_col]):
            print(f"Could not find required columns in table {litellm_table}")
            print(f"    Available columns: {columns}")
            print("Bedrock model cleanup completed! 0 Bedrock models updated (LiteLLM table structure unknown)")
            # Return success response for CloudFormation CustomResource
            return {"Status": "SUCCESS", "PhysicalResourceId": "bedrock-auth-cleanup", "Data": {"ModelsUpdated": "0"}}

        # Query all models from the LiteLLM database
        cursor.execute(
            psycopg2.sql.SQL("SELECT {}, {}, {} FROM {}").format(  # noqa: S608
                psycopg2.sql.Identifier(model_id_col),
                psycopg2.sql.Identifier(model_name_col),
                psycopg2.sql.Identifier(litellm_params_col),
                psycopg2.sql.Identifier(litellm_table),
            )
        )
        models = cursor.fetchall()

        print(f"Found {len(models)} total models in LiteLLM database")

        # Get all models from DynamoDB and check if they exist in LiteLLM
        dynamodb_models = get_all_dynamodb_models()
        bedrock_models_processed = 0

        for dynamodb_model in dynamodb_models:
            dynamodb_model_id = dynamodb_model["model_id"]
            dynamodb_model_name = dynamodb_model["model_name"]

            # Check if this is a Bedrock model
            if not dynamodb_model_name.startswith("bedrock/"):
                continue

            print(f"Processing Bedrock model: {dynamodb_model_name}")

            # Find the corresponding LiteLLM model by matching the model_name (alias)
            # DynamoDB model_id is actually the alias, LiteLLM model_name is the alias
            matching_litellm_model = None
            for model_id, model_name, litellm_params_data in models:
                # Check if this LiteLLM model_name matches our DynamoDB model_id (which is the alias)
                if model_name == dynamodb_model_id:
                    try:
                        # Handle both dict and JSON string formats
                        if isinstance(litellm_params_data, dict):
                            litellm_params = litellm_params_data
                        elif isinstance(litellm_params_data, str):
                            litellm_params = json.loads(litellm_params_data) if litellm_params_data else {}
                        else:
                            litellm_params = {}
                    except json.JSONDecodeError:
                        continue

                    matching_litellm_model = {
                        "model_id": model_id,
                        "model_name": model_name,
                        "litellm_params": litellm_params,
                    }
                    break

            if not matching_litellm_model:
                print(f"No matching LiteLLM model found for: {dynamodb_model_name}")
                continue

            # Check if this model has an api_key to remove
            if "api_key" in matching_litellm_model["litellm_params"]:
                print(f"Removing api_key from: {matching_litellm_model['model_name']}")

                try:
                    # Remove api_key from litellm_params
                    clean_params = matching_litellm_model["litellm_params"].copy()
                    if "api_key" in clean_params:  # pragma: allowlist secret
                        del clean_params["api_key"]

                    # Update the model in the database
                    clean_params_json = json.dumps(clean_params)
                    cursor.execute(
                        psycopg2.sql.SQL("UPDATE {} SET {} = %s WHERE {} = %s").format(  # noqa: S608
                            psycopg2.sql.Identifier(litellm_table),
                            psycopg2.sql.Identifier(litellm_params_col),
                            psycopg2.sql.Identifier(model_id_col),
                        ),
                        (clean_params_json, matching_litellm_model["model_id"]),
                    )
                    print(f"Successfully cleaned model: {matching_litellm_model['model_name']}")
                    bedrock_models_processed += 1

                except Exception as e:
                    print(f"Error cleaning model {matching_litellm_model['model_name']}: {e}")
                    conn.rollback()
            else:
                print(f"Model {matching_litellm_model['model_name']} already clean")

        # Commit the changes
        conn.commit()
        print(f"Cleanup completed! {bedrock_models_processed} Bedrock models processed")

        # Return success response for CloudFormation CustomResource
        return {
            "Status": "SUCCESS",
            "PhysicalResourceId": "bedrock-auth-cleanup",
            "Data": {"ModelsUpdated": str(bedrock_models_processed)},
        }

    except ValueError as e:
        # Handle configuration/validation errors
        print(f"Configuration error: {e}")
        return {"Status": "FAILED", "PhysicalResourceId": "bedrock-auth-cleanup", "Reason": str(e)}

    except Exception as e:
        # Handle unexpected errors
        print(f"Cleanup failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")

        # Rollback any pending database changes
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                print(f"Failed to rollback database changes: {rollback_error}")

        return {"Status": "FAILED", "PhysicalResourceId": "bedrock-auth-cleanup", "Reason": str(e)}

    finally:
        # Ensure proper cleanup of database resources
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")

        if conn:
            try:
                conn.close()
            except Exception as e:
                print(f"Error closing database connection: {e}")
