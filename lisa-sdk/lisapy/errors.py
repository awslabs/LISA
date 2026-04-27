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

"""Custom errors."""

from typing import Protocol, runtime_checkable, Union


@runtime_checkable
class _SyncResponse(Protocol):
    """Minimal protocol for sync HTTP response objects (e.g. requests.Response)."""

    status_code: int

    def json(self) -> object: ...


ErrorResponse = Union[_SyncResponse, str, dict, list, None]


class RateLimitExceededError(Exception):
    """Rate limit exceeded exception."""

    def __init__(self, message: object) -> None:
        super().__init__(message)


class NotFoundError(Exception):
    """Not found exception."""

    def __init__(self, message: object) -> None:
        super().__init__(message)


class ModelEndpointError(Exception):
    """Model endpoint error exception."""

    def __init__(self, message: object) -> None:
        super().__init__(message)


class UnknownError(Exception):
    """Unknown error exception."""

    def __init__(self, message: object) -> None:
        super().__init__(message)


def parse_error(status_code: int, response: ErrorResponse = None) -> Exception:
    """Parse error given an HTTP status code and an optional API response.

    Works with both requests.Response (sync) and aiohttp.ClientResponse (async).
    For async callers, pass the status code directly — response body extraction
    should be done before calling this function since response.json() is async.

    Parameters
    ----------
    status_code : int
        HTTP status code.

    response : ErrorResponse, optional
        API response object (requests.Response) or pre-extracted error message.

    Returns:
    -------
    Exception
        Parsed exception.
    """
    message: object = "An error occurred with no additional information."
    if response is not None:
        if isinstance(response, (str, dict, list)):
            message = response
        elif isinstance(response, _SyncResponse):
            try:
                message = response.json()
            except Exception:
                message = "An error occurred with no additional information."

    if status_code == 404:
        return NotFoundError(message)
    if status_code == 429:
        return RateLimitExceededError(message)
    if status_code == 500:
        return ModelEndpointError(message)

    return UnknownError(message)
