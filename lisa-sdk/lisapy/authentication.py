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

"""Cognito Authentication Helper."""
import getpass
from typing import Any, Dict

import boto3


def get_cognito_token(client_id: str, username: str, region: str = "us-east-1") -> Dict[str, Any]:
    """Get a token from Cognito.

    Parameters
    ----------
    client_id : str
        Cognito client ID.

    username : str
        Cognito username.

    region : str, default="us-east-1"
        AWS region.

    Returns
    -------
    Dict[str, Any]
        Token response from cognito.
    """
    cognito = boto3.client("cognito-idp", region_name=region)
    token_response = cognito.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        ClientId=client_id,
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": getpass.getpass("Enter your password: "),
        },
    )
    return token_response  # type: ignore
