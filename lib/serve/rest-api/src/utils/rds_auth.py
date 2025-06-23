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
import os
from typing import cast
from urllib.parse import quote_plus

import boto3


def generate_auth_token(host: str, port: str, user: str) -> str:
    rds = boto3.client("rds", region_name=os.environ["AWS_REGION"])
    token = rds.generate_db_auth_token(DBHostname=host, Port=port, DBUsername=user)
    return quote_plus(token)


def _get_lambda_role_arn() -> str:
    """Get the ARN of the Lambda execution role.

    Returns
    -------
    str
        The full ARN of the Lambda execution role
    """
    sts = boto3.client("sts")
    identity = sts.get_caller_identity()
    return cast(str, identity["Arn"])  # This will include the role name


def get_lambda_role_name() -> str:
    """Extract the role name from the Lambda execution role ARN.

    Returns
    -------
    str
        The name of the Lambda execution role without the full ARN
    """
    arn = _get_lambda_role_arn()
    parts = arn.split(":assumed-role/")[1].split("/")
    return parts[0]  # This is the role name
