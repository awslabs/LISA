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

import json
import logging
import os
from collections.abc import Iterator
from typing import Union

import boto3
import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.status import HTTP_401_UNAUTHORIZED

from ....auth import Authorizer, extract_user_groups_from_jwt
from ....utils.guardrails import (
    create_guardrail_json_response,
    create_guardrail_streaming_response,
    extract_guardrail_response,
    get_applicable_guardrails,
    get_model_guardrails,
    is_guardrail_violation,
)
from ....utils.metrics import publish_metrics_event

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
    # Model Info
    "model/info",
    "v1/model/info",
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
    # MCP
    "mcp/enabled",
    "mcp/tools/list",
    "mcp/tools/call",
    "v1/mcp/server",
)

# With the introduction of the LiteLLM database for model configurations, it forces a requirement to have a
# LiteLLM-vended API key. Since we are not requiring LiteLLM keys for customers, we are using the LiteLLM key
# required for the db and injecting that into all requests instead to overcome that requirement.
LITELLM_KEY = os.environ["LITELLM_KEY"]

secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])

logger = logging.getLogger(__name__)

router = APIRouter()


async def apply_guardrails_to_request(params: dict, model_id: str, jwt_data: dict) -> None:
    """
    Apply guardrails to a chat completion request.

    This function modifies the params dict in-place, adding applicable guardrails
    based on the user's group membership and the model's guardrail configuration.

    Args:
        params: The request parameters dict to modify
        model_id: The model ID to get guardrails for
        jwt_data: JWT data containing user information

    Raises:
        No exceptions are raised - errors are logged and the request continues
    """
    try:
        # Get guardrails for this model
        guardrails = await get_model_guardrails(model_id)

        if not guardrails:
            return

        # Extract user groups from JWT
        user_groups = extract_user_groups_from_jwt(jwt_data)

        # Determine which guardrails apply to this user
        applicable_guardrail_names = get_applicable_guardrails(user_groups, guardrails, model_id)

        # Add guardrails to request if any apply
        if applicable_guardrail_names:
            params["guardrails"] = applicable_guardrail_names
            logger.info(f"Applying guardrails to model {model_id}: {applicable_guardrail_names}")

    except Exception as e:
        logger.error(f"Error applying guardrails for model {model_id}: {e}")
        # Continue with request even if guardrails fail to apply


def handle_guardrail_violation_response(
    response: requests.Response, model_id: str, params: dict, is_streaming: bool
) -> Response | None:
    """
    Handle guardrail violation errors in LiteLLM responses.

    Checks if a 400 error response contains a guardrail violation and converts it
    into an appropriate format (streaming or non-streaming).

    Args:
        response: The HTTP response from LiteLLM
        model_id: The model ID from the request
        params: The original request parameters
        is_streaming: Whether this is a streaming request

    Returns:
        Response object if a guardrail violation was handled, None otherwise
    """
    if response.status_code != 400:
        return None

    try:
        error_response = response.json()
        error_msg = error_response.get("error", {}).get("message", "")

        if not is_guardrail_violation(error_msg):
            return None

        logger.info("Guardrail policy violated")

        guardrail_response = extract_guardrail_response(error_msg)
        if not guardrail_response:
            return None

        created = int(error_response.get("created", 0) if is_streaming else params.get("created", 0))

        if is_streaming:
            # Return as streaming response
            return StreamingResponse(
                create_guardrail_streaming_response(guardrail_response, model_id, created), status_code=200
            )
        else:
            # Return as a normal completion response
            return create_guardrail_json_response(guardrail_response, model_id, created)

    except Exception as e:
        logger.error(f"Error handling guardrail violation: {e}")
        return None


def generate_response(iterator: Iterator[Union[str, bytes]]) -> Iterator[str]:
    """For streaming responses, generate strings instead of bytes objects so that clients recognize the LLM output."""
    for line in iterator:
        if isinstance(line, bytes):
            line = line.decode()
        if line:
            yield f"{line}\n\n"


def generate_response_with_guardrail_handling(iterator: Iterator[Union[str, bytes]], model: str) -> Iterator[str]:
    """
    Generate streaming responses with guardrail violation error handling.

    This wrapper checks each chunk in the stream for guardrail violations and converts
    them into properly formatted streaming responses.
    """
    for line in iterator:
        if isinstance(line, bytes):
            line = line.decode()

        if not line:
            continue

        # Check if this line contains an error (SSE format: "data: {...}")
        if line.startswith("data: "):
            try:
                # Extract JSON from SSE data line
                data_content = line[6:].strip()  # Remove "data: " prefix

                # Skip [DONE] marker
                if data_content == "[DONE]":
                    yield f"{line}\n\n"
                    continue

                # Try to parse as JSON to check for errors
                chunk_data = json.loads(data_content)

                # Check if this is an error chunk
                if "error" in chunk_data:
                    error_msg = chunk_data.get("error", {}).get("message", "")

                    if is_guardrail_violation(error_msg):
                        logger.info("Guardrail policy violated in streaming response")

                        guardrail_response = extract_guardrail_response(error_msg)
                        if guardrail_response:
                            # Stream the guardrail response
                            created = int(chunk_data.get("created", 0))
                            for chunk in create_guardrail_streaming_response(guardrail_response, model, created):
                                yield chunk
                            return  # Stop streaming after guardrail response
                        else:
                            # Could not extract guardrail response, pass through the error
                            yield f"{line}\n\n"
                    else:
                        # Different error, pass it through
                        yield f"{line}\n\n"
                else:
                    # Normal chunk, pass it through
                    yield f"{line}\n\n"

            except json.JSONDecodeError:
                # Not valid JSON or not in expected format, pass through as-is
                yield f"{line}\n\n"
        else:
            # Not in SSE format, pass through as-is
            yield f"{line}\n\n"


@router.api_route("/{api_path:path}", methods=["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE", "HEAD"])
async def litellm_passthrough(request: Request, api_path: str) -> Response:
    """
    Pass requests directly to LiteLLM. LiteLLM and deployed models will respond here directly.

    This accepts all HTTP methods as to not put any restriction on how deployed models would act given different HTTP
    payload requirements. Results are only streamed if the OpenAI-compatible request specifies streaming as part of the
    input payload.
    """
    litellm_path = f"{LITELLM_URL}/{api_path}"
    headers = dict(request.headers.items())

    authorizer = Authorizer()
    require_admin = api_path not in OPENAI_ROUTES
    jwt_data = await authorizer.authenticate_request(request)
    if not await authorizer.can_access(request, require_admin):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, message="Not authenticated in litellm_passthrough")

    # At this point in the request, we have already validated auth with IdP or persistent token. By using LiteLLM for
    # model management, LiteLLM requires an admin key, and that forces all requests to require a key as well. To avoid
    # soliciting yet another form of auth from the user, we add the existing LiteLLM key to the headers that go directly
    # to the LiteLLM instance.
    headers["Authorization"] = f"Bearer {LITELLM_KEY}"

    http_method = request.method
    if http_method == "GET" or http_method == "DELETE":
        response = requests.request(method=http_method, url=litellm_path, headers=headers)
        return JSONResponse(response.json(), status_code=response.status_code)
    # not a GET or DELETE request, so expect a JSON payload as part of the request
    params = await request.json()

    # Apply guardrails for chat/completions requests
    if api_path in ["chat/completions", "v1/chat/completions"]:
        model_id = params.get("model")
        if model_id:
            await apply_guardrails_to_request(params, model_id, jwt_data)

    if params.get("stream", False):  # if a streaming request
        response = requests.request(method=http_method, url=litellm_path, json=params, headers=headers, stream=True)

        # Check for guardrail violations
        model_id = params.get("model", "")
        guardrail_response = handle_guardrail_violation_response(response, model_id, params, is_streaming=True)
        if guardrail_response:
            return guardrail_response

        # Publish metrics for streaming chat completions (API users)
        if api_path in ["chat/completions", "v1/chat/completions"] and response.status_code == 200:
            publish_metrics_event(request, params, response.status_code)

        # Normal streaming (no error or non-guardrail error)
        # Use guardrail-aware generator for chat/completions endpoints
        if api_path in ["chat/completions", "v1/chat/completions"]:
            model_id = params.get("model", "")
            return StreamingResponse(
                generate_response_with_guardrail_handling(response.iter_lines(), model_id),
                status_code=response.status_code,
            )
        else:
            return StreamingResponse(generate_response(response.iter_lines()), status_code=response.status_code)
    else:  # not a streaming request
        response = requests.request(method=http_method, url=litellm_path, json=params, headers=headers)

        # Check for guardrail violations
        model_id = params.get("model", "")
        guardrail_response = handle_guardrail_violation_response(response, model_id, params, is_streaming=False)
        if guardrail_response:
            return guardrail_response

        if response.status_code != 200:
            logger.error(f"LiteLLM error response: {response.text}")

        # Publish metrics for chat completions (API users)
        if api_path in ["chat/completions", "v1/chat/completions"]:
            publish_metrics_event(request, params, response.status_code)

        return JSONResponse(response.json(), status_code=response.status_code)
