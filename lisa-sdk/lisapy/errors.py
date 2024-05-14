"""
Handle errors.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
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
