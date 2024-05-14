"""
Authentication.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
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
