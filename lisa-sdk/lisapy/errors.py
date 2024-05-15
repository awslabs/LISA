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
from requests import Response


class RateLimitExceededError(Exception):
    """Rate limit exceeded exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class NotFoundError(Exception):
    """Not found exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ModelEndpointError(Exception):
    """Model endpoint error exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UnknownError(Exception):
    """Unknown error exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def parse_error(status_code: int, response: Response) -> Exception:
    """Parse error given an HTTP status code and an API response.

    Parameters
    ----------
    status_code : int
        HTTP status code.

    response : Response
        API response.

    Returns
    -------
    Exception
        Parsed exception.
    """
    status_code = response.status_code
    try:
        message = response.json()
    except ValueError:
        message = "An error occurred with no additional information."

    # Try to parse an inference error
    if status_code == 404:
        return NotFoundError(message)
    if status_code == 429:
        return RateLimitExceededError(message)
    if status_code == 500:
        return ModelEndpointError(message)

    # Fallback to an unknown error
    return UnknownError(message)
