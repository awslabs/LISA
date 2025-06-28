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

"""Lambda to rotate management secret."""

import json
import logging
import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from utilities.common_functions import retry_config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Secrets Manager rotation handler for management key.

    This function implements the standard AWS Secrets Manager rotation workflow:
    1. createSecret: Generate new secret version
    2. setSecret: Store the new secret
    3. testSecret: Validate the new secret works
    4. finishSecret: Make the new secret active
    """
    secret_arn = event.get("Step1", {}).get("SecretId") or event.get("SecretId")
    token = event.get("Step1", {}).get("ClientRequestToken") or event.get("ClientRequestToken")
    step = event.get("Step")

    if not secret_arn or not token:
        logger.error("SecretId and ClientRequestToken are required")
        raise ValueError("SecretId and ClientRequestToken are required")

    logger.info(f"Executing rotation step: {step} for secret: {secret_arn}")

    try:
        if step == "createSecret":
            create_secret(secret_arn, token)
        elif step == "setSecret":
            set_secret(secret_arn, token)
        elif step == "testSecret":
            test_secret(secret_arn, token)
        elif step == "finishSecret":
            finish_secret(secret_arn, token)
        else:
            logger.error(f"Invalid step parameter: {step}")
            raise ValueError(f"Invalid step parameter: {step}")

        return {"statusCode": 200, "body": json.dumps("Success")}

    except Exception as e:
        logger.error(f"Error during rotation step {step}: {str(e)}")
        raise


def create_secret(secret_arn: str, token: str) -> None:
    """
    Create a new secret version with a new randomly generated password.
    """
    logger.info(f"Creating new secret version for {secret_arn}")

    try:
        # Check if version already exists
        secrets_manager.get_secret_value(SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING")
        logger.info(f"Secret version {token} already exists")
        return
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise e

    # Generate new password
    try:
        response = secrets_manager.get_random_password(ExcludePunctuation=True, PasswordLength=16)
        new_password = response["RandomPassword"]

        # Put the new secret
        secrets_manager.put_secret_value(
            SecretId=secret_arn, ClientRequestToken=token, SecretString=new_password, VersionStages=["AWSPENDING"]
        )

        logger.info(f"Successfully created new secret version {token}")

    except ClientError as e:
        logger.error(f"Error creating secret: {e}")
        raise


def set_secret(secret_arn: str, token: str) -> None:
    """
    Set the secret in the service that the secret belongs to.
    For management keys, this step is typically a no-op since the secret
    is used by the application directly from Secrets Manager.
    """
    logger.info(f"Setting secret for {secret_arn} - No action needed for management key")
    # No action needed for management keys as they are retrieved directly from Secrets Manager


def test_secret(secret_arn: str, token: str) -> None:
    """
    Test the new secret to ensure it's valid and can be used.
    For management keys, we verify the secret can be retrieved and has the expected format.
    """
    logger.info(f"Testing secret for {secret_arn}")

    try:
        # Retrieve the new secret version
        response = secrets_manager.get_secret_value(SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING")

        new_secret = response["SecretString"]

        # Validate the secret format
        if not new_secret or len(new_secret) < 8:
            raise ValueError("New secret is invalid - too short or empty")

        # Additional validation - ensure it doesn't contain punctuation (as per generation config)
        if any(char in new_secret for char in "!@#$%^&*()_+-=[]{}|;:,.<>?"):  # noqa: P103
            raise ValueError("New secret contains punctuation when it shouldn't")

        logger.info(f"Secret test passed for version {token}")

    except ClientError as e:
        logger.error(f"Error testing secret: {e}")
        raise
    except ValueError as e:
        logger.error(f"Secret validation failed: {e}")
        raise


def finish_secret(secret_arn: str, token: str) -> None:
    """
    Finish the rotation by marking the new secret as current.
    """
    logger.info(f"Finishing secret rotation for {secret_arn}")

    try:
        # Get current version info
        metadata = secrets_manager.describe_secret(SecretId=secret_arn)
        current_version = None

        for version_id, version_info in metadata["VersionIdsToStages"].items():
            if "AWSCURRENT" in version_info:
                current_version = version_id
                break

        # Update version stages
        secrets_manager.update_secret_version_stage(
            SecretId=secret_arn,
            VersionStage="AWSCURRENT",
            ClientRequestToken=token,
            RemoveFromVersionId=current_version,
        )

        logger.info(f"Successfully finished rotation - version {token} is now current")

    except ClientError as e:
        logger.error(f"Error finishing secret rotation: {e}")
        raise


# Legacy function for backward compatibility
def rotate_management_key(event: dict, ctx: dict) -> None:
    """Legacy rotation function - deprecated, use handler instead."""
    logger.warning("rotate_management_key is deprecated, use handler instead")

    response = secrets_manager.get_random_password(ExcludePunctuation=True, PasswordLength=16)
    secrets_manager.put_secret_value(
        SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), SecretString=response["RandomPassword"]
    )
