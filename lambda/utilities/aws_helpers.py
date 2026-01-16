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

"""AWS-specific helper utilities."""

import logging
import os
import tempfile
from functools import cache
from typing import Any, cast, Union

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

# Boto3 retry configuration
retry_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",
    },
)

# Global SSM client
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)

# Global certificate file handle
_cert_file = None


@cache
def get_cert_path(iam_client: Any) -> Union[str, bool]:
    """
    Get certificate path for SSL validation against LISA Serve endpoint.

    This function retrieves IAM server certificates for SSL verification.
    For ACM certificates or when no certificate is specified, it returns
    True to use default verification.

    Parameters
    ----------
    iam_client : Any
        Boto3 IAM client instance.

    Returns
    -------
    Union[str, bool]
        Path to certificate file, or True to use default verification.

    Example
    -------
    >>> iam = boto3.client("iam")
    >>> cert_path = get_cert_path(iam)
    >>> if isinstance(cert_path, str):
    ...     # Use custom certificate
    ...     requests.get(url, verify=cert_path)
    ... else:
    ...     # Use default verification
    ...     requests.get(url, verify=True)
    """
    global _cert_file

    cert_arn = os.environ.get("RESTAPI_SSL_CERT_ARN")
    if not cert_arn:
        logger.info("No SSL certificate ARN specified, using default verification")
        return True

    # For ACM certificates, use default verification since they are trusted AWS certificates
    if ":acm:" in cert_arn:
        logger.info("ACM certificate detected, using default SSL verification")
        return True

    try:
        # Clean up previous cert file if it exists
        if _cert_file and os.path.exists(_cert_file.name):
            try:
                os.unlink(_cert_file.name)
            except Exception as e:
                logger.warning(f"Failed to clean up previous cert file: {e}")

        # Get the certificate name from the ARN
        cert_name = cert_arn.split("/")[1]
        logger.info(f"Retrieving certificate '{cert_name}' from IAM")

        # Get the certificate from IAM
        rest_api_cert = iam_client.get_server_certificate(ServerCertificateName=cert_name)
        cert_body = rest_api_cert["ServerCertificate"]["CertificateBody"]

        # Create a new temporary file
        _cert_file = tempfile.NamedTemporaryFile(delete=False)
        _cert_file.write(cert_body.encode("utf-8"))
        _cert_file.flush()

        logger.info(f"Certificate saved to temporary file: {_cert_file.name}")
        return _cert_file.name

    except Exception as e:
        logger.error(f"Failed to get certificate from IAM: {e}", exc_info=True)
        # If we fail to get the cert, return True to fall back to default verification
        return True


@cache
def get_rest_api_container_endpoint() -> str:
    """
    Get REST API container base URI from SSM Parameter Store.

    Returns
    -------
    str
        The REST API container endpoint URL.

    Example
    -------
    >>> endpoint = get_rest_api_container_endpoint()
    >>> endpoint
    'https://api.example.com/v1/serve'
    """
    lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
    lisa_api_endpoint = lisa_api_param_response["Parameter"]["Value"]
    return f"{lisa_api_endpoint}/{os.environ['REST_API_VERSION']}/serve"


def _get_lambda_role_arn() -> str:
    """
    Get the ARN of the Lambda execution role.

    Returns
    -------
    str
        The full ARN of the Lambda execution role.

    Example
    -------
    >>> _get_lambda_role_arn()
    'arn:aws:sts::123456789012:assumed-role/MyLambdaRole/MyFunction'
    """
    sts = boto3.client("sts", region_name=os.environ["AWS_REGION"])
    identity = sts.get_caller_identity()
    return cast(str, identity["Arn"])


def get_lambda_role_name() -> str:
    """
    Extract the role name from the Lambda execution role ARN.

    Returns
    -------
    str
        The name of the Lambda execution role without the full ARN.

    Example
    -------
    >>> get_lambda_role_name()
    'MyLambdaRole'
    """
    arn = _get_lambda_role_arn()
    parts = arn.split(":assumed-role/")[1].split("/")
    return parts[0]


def get_account_and_partition() -> tuple[str, str]:
    """
    Get AWS account ID and partition from environment or ECR repository ARN.

    Returns
    -------
    tuple[str, str]
        Tuple of (account_id, partition).

    Example
    -------
    >>> account_id, partition = get_account_and_partition()
    >>> account_id
    '123456789012'
    >>> partition
    'aws'
    """
    account_id = os.environ.get("AWS_ACCOUNT_ID", "")
    partition = os.environ.get("AWS_PARTITION", "aws")

    if not account_id:
        ecr_repo_arn = os.environ.get("ECR_REPOSITORY_ARN", "")
        if ecr_repo_arn:
            arn_parts = ecr_repo_arn.split(":")
            partition = arn_parts[1]
            account_id = arn_parts[4]

    return account_id, partition
