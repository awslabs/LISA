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

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3

from .session_models import AwsSessionRecord


class InvalidAwsCredentialsError(Exception):
    """Raised when provided AWS credentials are invalid or STS rejects them."""


@dataclass
class AwsStsClient:
    """
    Thin wrapper around boto3 STS client for validating credentials and
    creating short-lived session credentials.
    """

    def _create_sts_client(
        self,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None,
        region: str,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "region_name": region,
            # Use the regional STS endpoint so traffic stays within the VPC
            # when an STS VPC endpoint is configured (the global endpoint
            # sts.amazonaws.com is not reachable from private subnets).
            "endpoint_url": f"https://sts.{region}.amazonaws.com",
        }
        if session_token:
            kwargs["aws_session_token"] = session_token
        return boto3.client("sts", **kwargs)

    def validate_static_credentials(
        self,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None,
        region: str,
    ) -> tuple[str, str]:
        """
        Validate credentials via GetCallerIdentity.

        Returns (account_id, arn) on success, raises InvalidAwsCredentialsError on failure.
        """
        sts = self._create_sts_client(access_key_id, secret_access_key, session_token, region)
        try:
            identity = sts.get_caller_identity()
        except Exception as exc:  # noqa: BLE001
            raise InvalidAwsCredentialsError(f"STS GetCallerIdentity failed: {type(exc).__name__}: {exc}") from exc

        account_id = str(identity.get("Account"))
        arn = str(identity.get("Arn"))
        return account_id, arn

    # AWS STS temporary credentials can last at most 12 hours.
    MAX_TEMP_CREDENTIAL_TTL_SECONDS = 43200

    def create_session_credentials(
        self,
        user_id: str,
        session_id: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None,
        region: str,
        duration_seconds: int = 3600,
        safety_margin_seconds: int = 60,
    ) -> AwsSessionRecord:
        """
        Produce an AwsSessionRecord from the provided credentials.

        * **Long-term (IAM user) credentials** (no session_token): calls
          ``GetSessionToken`` to mint short-lived temporary credentials
          lasting ``duration_seconds``.
        * **Temporary credentials** (session_token present): stores them
          directly -- AWS forbids calling ``GetSessionToken`` with
          temporary credentials.  There is no STS API to query when
          pre-existing temporary credentials expire, so we assume the
          maximum STS lifetime (12 h).  The credentials will naturally
          fail at call time once they truly expire.

        The returned record's ``expires_at`` is adjusted by
        ``safety_margin_seconds``.
        """
        now = datetime.now(timezone.utc)

        if session_token:
            # We cannot determine the real expiration of caller-provided
            # temporary credentials, so assume the STS maximum (12 h).
            # The credentials will fail with an auth error at call time
            # once they truly expire, prompting the user to reconnect.
            assumed_ttl = self.MAX_TEMP_CREDENTIAL_TTL_SECONDS
            expires_at = now + timedelta(seconds=assumed_ttl - safety_margin_seconds)
            return AwsSessionRecord(
                user_id=user_id,
                session_id=session_id,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                aws_session_token=session_token,
                aws_region=region,
                expires_at=expires_at,
            )

        # Long-term IAM user credentials -- mint a session via STS
        sts = self._create_sts_client(access_key_id, secret_access_key, None, region)
        try:
            response = sts.get_session_token(DurationSeconds=duration_seconds)
        except Exception as exc:  # noqa: BLE001
            raise InvalidAwsCredentialsError(f"STS GetSessionToken failed: {type(exc).__name__}: {exc}") from exc

        creds: dict[str, Any] = response["Credentials"]
        raw_expiration: datetime = creds["Expiration"]
        if raw_expiration.tzinfo is None:
            raw_expiration = raw_expiration.replace(tzinfo=timezone.utc)
        expires_at = raw_expiration - timedelta(seconds=safety_margin_seconds)

        if expires_at <= now:
            expires_at = now + timedelta(seconds=1)

        return AwsSessionRecord(
            user_id=user_id,
            session_id=session_id,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            aws_region=region,
            expires_at=expires_at,
        )
