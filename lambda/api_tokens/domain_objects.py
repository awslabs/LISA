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

from datetime import timedelta

from pydantic import BaseModel, Field, field_validator
from utilities.time import now_seconds


def default_expiration() -> int:
    """Calculate default token expiration (90 days from now)"""
    return now_seconds() + int(timedelta(days=90).total_seconds())


class CreateTokenAdminRequest(BaseModel):
    """Admin request to create token for a user or system"""

    tokenExpiration: int = Field(
        default_factory=default_expiration, description="Unix timestamp when token expires. Defaults to 90 days"
    )
    groups: list[str] = Field(default_factory=list, description="Groups for the token")
    name: str = Field(description="Human-readable name for the token")
    isSystemToken: bool = Field(default=False, description="Whether this is a system token")

    @field_validator("tokenExpiration")
    @classmethod
    def validate_expiration(cls, v: int) -> int:
        current_time = now_seconds()
        if v <= current_time:
            raise ValueError("tokenExpiration must be in the future")
        return v


class CreateTokenUserRequest(BaseModel):
    """User request to create their own token"""

    name: str = Field(description="Human-readable name for the token")
    tokenExpiration: int = Field(
        default_factory=default_expiration, description="Unix timestamp when token expires. Defaults to 90 days"
    )

    @field_validator("tokenExpiration")
    @classmethod
    def validate_expiration(cls, v: int) -> int:
        current_time = now_seconds()
        if v <= current_time:
            raise ValueError("tokenExpiration must be in the future")
        return v


class CreateTokenResponse(BaseModel):
    token: str = Field(description="The actual token (only shown once!)")
    tokenUUID: str = Field(description="Unique identifier for the token")
    tokenExpiration: int
    createdDate: int
    username: str
    name: str
    groups: list[str]
    isSystemToken: bool


class TokenInfo(BaseModel):
    """Token information (without the actual token value)"""

    tokenUUID: str
    tokenExpiration: int
    createdDate: int
    username: str
    createdBy: str
    name: str
    groups: list[str]
    isSystemToken: bool
    isExpired: bool
    isLegacy: bool = False


class ListTokensResponse(BaseModel):
    tokens: list[TokenInfo]


class DeleteTokenResponse(BaseModel):
    message: str
    tokenUUID: str
