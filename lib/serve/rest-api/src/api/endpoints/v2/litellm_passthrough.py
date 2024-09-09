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

"""Model invocation routes."""

import logging
import os
from collections.abc import Iterator
from typing import Union

import boto3
import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.status import HTTP_401_UNAUTHORIZED

from ....auth import get_authorization_token, get_jwks_client, id_token_is_valid, is_admin, is_idp_used

# Local LiteLLM installation URL. By default, LiteLLM runs on port 4000. Change the port here if the
# port was changed as part of the LiteLLM startup in entrypoint.sh
LITELLM_URL = "http://localhost:4000"

# The following is an allowlist of OpenAI routes that users would not need elevated permissions to invoke. This is so
# that we may assume anything *not* in this allowlist is an admin operation that requires greater LiteLLM permissions.
# Assume that anything not within these routes requires admin permissions, which would only come from the LISA model
# management API.
OPENAI_ROUTES = (
    # List models
    "models",
    "v1/models",
    # Text completions
    "chat/completions",
    "v1/chat/completions",
    "completions",
    "v1/completions",
    # Embeddings
    "embeddings",
    "v1/embeddings",
    # Create images
    "images/generations",
    "v1/images/generations",
    # Audio routes
    "audio/speech",
    "v1/audio/speech",
    "audio/transcriptions",
    "v1/audio/transcriptions",
    # Health check routes
    "health",
    "health/readiness",
    "health/liveliness",
)

# With the introduction of the LiteLLM database for model configurations, it forces a requirement to have a
# LiteLLM-vended API key. Since we are not requiring LiteLLM keys for customers, we are using the LiteLLM key
# required for the db and injecting that into all requests instead to overcome that requirement.
LITELLM_KEY = os.environ["LITELLM_KEY"]

secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])

logger = logging.getLogger(__name__)

router = APIRouter()


def generate_response(iterator: Iterator[Union[str, bytes]]) -> Iterator[str]:
    """For streaming responses, generate strings instead of bytes objects so that clients recognize the LLM output."""
    for line in iterator:
        if isinstance(line, bytes):
            line = line.decode()
        if line:
            yield f"{line}\n\n"


@router.api_route(
    "/{api_path:path}", methods=["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE", "HEAD"]
)  # type: ignore
async def litellm_passthrough(request: Request, api_path: str) -> Response:
    """
    Pass requests directly to LiteLLM. LiteLLM and deployed models will respond here directly.

    This accepts all HTTP methods as to not put any restriction on how deployed models would act given different HTTP
    payload requirements. Results are only streamed if the OpenAI-compatible request specifies streaming as part of the
    input payload.
    """
    litellm_path = f"{LITELLM_URL}/{api_path}"
    headers = dict(request.headers.items())

    print(f"HEADERS OBJ {headers}")

    logger.info("attempting passthrough")
    print("attempting passthrough")
    if not is_valid_management_token(headers):
        logger.info("mgmt token not valid")
        print("mgmt token not valid")
        # If not handling an OpenAI request, we will also check if the user is an Admin user before allowing the
        # request, otherwise, we will block it. This prevents non-admins from invoking model management APIs
        # directly. If LISA Serve is deployed without an IdP configuration, we cannot determine who is an admin
        # user, so all API routes will default to being openly accessible.
        if api_path not in OPENAI_ROUTES and is_idp_used():
            client_id = os.environ.get("CLIENT_ID", "")
            authority = os.environ.get("AUTHORITY", "")
            admin_group = os.environ.get("ADMIN_GROUP", "")
            jwt_groups_property = os.environ.get("JWT_GROUPS_PROP", "")

            id_token = get_authorization_token(headers=headers, header_name="Authorization")
            jwks_client = get_jwks_client()
            if jwt_data := id_token_is_valid(
                id_token=id_token, authority=authority, client_id=client_id, jwks_client=jwks_client
            ):
                if not is_admin(jwt_data=jwt_data, admin_group=admin_group, jwt_groups_property=jwt_groups_property):
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated in passthrough - 125"
                    )
            else:
                raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated in passthrough - 127")

    # At this point in the request, we have already validated auth with IdP or persistent token. By using LiteLLM for
    # model management, LiteLLM requires an admin key, and that forces all requests to require a key as well. To avoid
    # soliciting yet another form of auth from the user, we add the existing LiteLLM key to the headers that go directly
    # to the LiteLLM instance.
    headers["Authorization"] = f"Bearer {LITELLM_KEY}"
    logger.info(f"overriding authorization token with {LITELLM_KEY}")
    print(f"overriding authorization token with {LITELLM_KEY}")

    http_method = request.method
    if http_method == "GET":
        return JSONResponse(requests.request(method=http_method, url=litellm_path, headers=headers).json())
    # not a GET request, so expect a JSON payload as part of the request
    params = await request.json()
    if params.get("stream", False):  # if a streaming request
        response = requests.request(method=http_method, url=litellm_path, json=params, headers=headers, stream=True)
        return StreamingResponse(generate_response(response.iter_lines()))
    else:  # not a streaming request
        return JSONResponse(requests.request(method=http_method, url=litellm_path, json=params, headers=headers).json())


def refresh_management_tokens() -> list[str]:
    """Return DDB entry for token if it exists."""
    secret_tokens = []

    try:
        secret_tokens.append(
            secrets_manager.get_secret_value(SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT")[
                "SecretString"
            ]
        )
        secret_tokens.append(
            secrets_manager.get_secret_value(
                SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSPREVIOUS"
            )["SecretString"]
        )
    except Exception:
        logger.info(f"No previous secret version for {os.environ.get('MANAGEMENT_KEY_NAME')}")

    return secret_tokens


def is_valid_management_token(headers: dict[str, str]) -> bool:
    """Return if API Token from request headers is valid if found."""
    secret_tokens = refresh_management_tokens()
    token = get_authorization_token(headers=headers, header_name="Authorization").strip()
    logger.info(f"Checking if {token} is in {secret_tokens}")

    print(f"Headers in is_valid_management_token {headers}")
    print(f"Headers in is_valid_management_token {headers}")

    print(f"Checking if {token} is in {secret_tokens}")
    return token in secret_tokens
