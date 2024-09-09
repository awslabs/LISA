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

import os

import boto3
from utilities.common_functions import retry_config

secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)


def rotate_management_key(event: dict, ctx: dict) -> None:
    """Rotates a key."""
    response = secrets_manager.get_random_password(
        SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), ExcludePunctuation=True, PasswordLength=16
    )
    secrets_manager.put_secret_value(
        SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), SecretString=response.RandomPassword
    )
    # try:
    #     # Retrieve the secret value
    #     response = secretsmanager.get_secret_value(SecretId=os.environ.get("MANAGEMENT_KEY_NAME"))

    #     # Check if the secret is in plaintext or in JSON format
    #     if 'SecretString' in response:
    #         return response['SecretString']
    #     else:
    #         import base64
    #         secret_binary = base64.b64decode(response['SecretBinary'])
    #         return secret_binary.decode('utf-8')

    # except ClientError as e:
    #     # Handle ResourceNotFoundException specifically
    #     if e.response['Error']['Code'] == 'ResourceNotFoundException':
    #         print(f"Secret with name '{secret_name}' not found.")
    #     else:
    #         print(f"Unexpected error: {e}")
    #     return None
