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

from __future__ import annotations

import logging
from datetime import timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from . import shared_session_store as _session_store
from . import shared_sts_client as _sts_client
from .identity import decode_jwt_payload
from .session_models import AwsSessionRecord
from .sts_client import InvalidAwsCredentialsError

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_identity_from_request(request: Request) -> tuple[str, str]:
    """
    Extract (user_id, session_id) from the authenticated request.

    user_id is derived from the JWT ``sub`` claim in the Authorization
    header (already verified by OIDCHTTPBearer middleware).
    session_id comes from the ``X-Session-Id`` header sent by the frontend.
    """
    # request.headers is case-insensitive; avoid converting to a plain dict
    hdrs = request.headers

    # --- user_id: prefer explicit header, fall back to JWT sub claim ---
    user_id: str | None = hdrs.get("x-user-id")
    if not user_id:
        auth_header = hdrs.get("authorization", "")
        token = auth_header.removeprefix("Bearer").strip() if auth_header else ""
        if token:
            claims = decode_jwt_payload(token)
            user_id = claims.get("sub")
            logger.debug("Extracted user_id=%s from JWT sub claim", user_id)

    # --- session_id from header ---
    session_id = hdrs.get("x-session-id")

    if not user_id or not session_id:
        missing = []
        if not user_id:
            missing.append("user_id (no JWT sub claim or X-User-Id header)")
        if not session_id:
            missing.append("session_id (no X-Session-Id header)")
        detail = f"Missing: {'; '.join(missing)}"
        logger.warning("Identity extraction failed: %s", detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    return user_id, session_id


@router.post("/connect", status_code=status.HTTP_200_OK)
async def connect_aws(request: Request) -> dict[str, Any]:
    """
    Accept AWS static credentials, validate them, and create a short-lived STS session.

    Request body:
      - accessKeyId: str
      - secretAccessKey: str
      - sessionToken?: str
      - region: str
    """
    user_id, session_id = _get_identity_from_request(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be valid JSON.",
        )

    access_key_id = body.get("accessKeyId")
    secret_access_key = body.get("secretAccessKey")
    session_token = body.get("sessionToken")
    region = body.get("region")

    if not access_key_id or not secret_access_key or not region:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="accessKeyId, secretAccessKey, and region are required.",
        )

    try:
        account_id, arn = _sts_client.validate_static_credentials(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
            region=region,
        )
    except InvalidAwsCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "InvalidCredentials", "message": str(exc)},
        ) from exc

    # For permanent (IAM user) credentials, duration_seconds controls the
    # GetSessionToken TTL.  For temporary credentials the param is ignored
    # and the session record uses the STS maximum (12 h) since we cannot
    # determine the real expiration of caller-provided temp creds.
    record: AwsSessionRecord = _sts_client.create_session_credentials(
        user_id=user_id,
        session_id=session_id,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
        region=region,
        duration_seconds=3600,
    )

    _session_store.set_session(record)

    return {
        "accountId": account_id,
        "arn": arn,
        "expiresAt": record.expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/status", status_code=status.HTTP_200_OK)
async def aws_status(request: Request) -> dict[str, Any]:
    """Return current AWS connection status for the user/session."""
    user_id, session_id = _get_identity_from_request(request)
    record = _session_store.get_session(user_id, session_id)

    if not record:
        return {"connected": False}

    return {
        "connected": True,
        "expiresAt": record.expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.delete("/connect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_aws(request: Request) -> Response:
    """Explicitly clear AWS session credentials for the user/session."""
    user_id, session_id = _get_identity_from_request(request)
    _session_store.delete_session(user_id, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
