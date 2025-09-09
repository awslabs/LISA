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

"""Common helper functions for RAG Lambdas."""
import copy
import functools
import json
import logging
import os
import tempfile
from contextvars import ContextVar
from decimal import Decimal
from functools import cache
from typing import Any, Callable, cast, Dict, List, TypeVar, Union

import boto3
from botocore.config import Config

from . import create_env_variables  # noqa type: ignore

retry_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",
    },
)
ctx_context: ContextVar[Any] = ContextVar("lamdbacontext")
F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger(__name__)
logging_configured = False

ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


class LambdaContextFilter(logging.Filter):
    """Filter for logging to include request id and function name."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter for logging to include request id and function name.

        Parameters
        ----------
        record : logging.LogRecord
            The log record.

        Returns
        -------
        bool
            A boolean.
        """
        try:
            context = ctx_context.get()
            record.requestid = context.aws_request_id
            record.functionname = context.function_name
        except Exception:
            record.requestid = "RID-MISSING"
            record.functionname = "FN-MISSING"
        return True


def setup_root_logging() -> None:
    """Configure root logger to include request id and function name."""
    global logging_configured

    if not logging_configured:
        logging_level = logging.INFO
        format_string = "%(asctime)s %(name)s [%(requestid)s] [%(levelname)s] %(message)s"

        root_logger = logging.getLogger()
        # Remove default handlers
        if root_logger.handlers:
            for handler in root_logger.handlers:
                root_logger.removeHandler(handler)

        root_logger = logging.getLogger()
        root_logger.setLevel(logging_level)
        handler = logging.StreamHandler()
        handler.setLevel(logging_level)
        formatter = logging.Formatter(format_string)
        handler.setFormatter(formatter)
        handler.addFilter(LambdaContextFilter())
        root_logger.addHandler(handler)
        logging_configured = True


setup_root_logging()


def _sanitize_event(event: Dict[str, Dict[str, Any]]) -> str:
    """Sanitize event before logging.

    Parameters
    ----------
    event : Dict[str, Dict[str, Any]]
        The lambda event.

    Returns
    -------
    str
        The sanitized event as a JSON-formatted string.
    """
    # First normalize keys for our object
    sanitized = copy.deepcopy(event)
    if "headers" in event:
        for key in event["headers"]:
            if key != key.lower():
                sanitized["headers"][key.lower()] = event["headers"][key]
                del sanitized["headers"][key]
    if "multiValueHeaders" in sanitized:
        for key in event["multiValueHeaders"]:
            if key != key.lower():
                sanitized["multiValueHeaders"][key.lower()] = event["multiValueHeaders"][key]
                del sanitized["multiValueHeaders"][key]

    if "headers" in sanitized and "authorization" in sanitized["headers"]:
        sanitized["headers"]["authorization"] = "<REDACTED>"
    if "multiValueHeaders" in sanitized and "authorization" in sanitized["headers"]:
        sanitized["multiValueHeaders"]["authorization"] = ["<REDACTED>"]
    return json.dumps(sanitized)


def api_wrapper(f: F) -> F:
    """Wrap the lambda function.

    Parameters
    ----------
    f : F
        The function to be wrapped.

    Returns
    -------
    F
        The wrapped function.
    """

    @functools.wraps(f)
    def wrapper(event: dict, context: dict) -> Dict[str, Union[str, int, Dict[str, str]]]:
        """Wrap Lambda event.

        Parameters
        ----------
        event : dict
            Lambda event.
        context : dict
            Lambda context.

        Returns
        -------
        Dict[str, Union[str, int, Dict[str, str]]]
            _description_
        """
        ctx_context.set(context)
        code_func_name = f.__name__
        lambda_func_name = context.function_name  # type: ignore [attr-defined]
        logger.info(f"Lambda {lambda_func_name}({code_func_name}) invoked with {_sanitize_event(event)}")
        try:
            result = f(event, context)
            return generate_html_response(200, result)
        except Exception as e:
            return generate_exception_response(e)

    return wrapper  # type: ignore [return-value]


def authorization_wrapper(f: F) -> F:
    """Wrap the lambda function.

    Parameters
    ----------
    f : F
        The function to be wrapped.

    Returns
    -------
    F
        The wrapped function.
    """

    @functools.wraps(f)
    def wrapper(event: dict, context: dict) -> F:
        """Wrap Lambda event.

        Parameters
        ----------
        event : dict
            Lambda event.
        context : dict
            Lambda context.

        Returns
        -------
        F
            The wrapped function.
        """
        ctx_context.set(context)
        return f(event, context)  # type: ignore [no-any-return]

    return wrapper  # type: ignore [return-value]


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def generate_html_response(status_code: int, response_body: dict) -> Dict[str, Union[str, int, Dict[str, str]]]:
    """Generate a response for an API call.

    Parameters
    ----------
    status_code : int
        HTTP status code.
    response_body : dict
        Response body.

    Returns
    -------
    Dict[str, Union[str, int, Dict[str, str]]]
        An HTML response.
    """
    return {
        "statusCode": status_code,
        "body": json.dumps(response_body, cls=DecimalEncoder),
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
            "Cache-Control": "no-store, no-cache",
            "Pragma": "no-cache",
            "Strict-Transport-Security": "max-age:47304000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    }


def generate_exception_response(
    e: Exception,
) -> Dict[str, Union[str, int, Dict[str, str]]]:
    """Generate a response for an exception used for all exceptions that are not caught by the API.

    Parameters
    ----------
    e : Exception
        Exception that was caught.

    Returns
    -------
    Dict[str, Union[str, int, Dict[str, str]]]
        An HTML response.
    """
    status_code = 400
    if hasattr(e, "response"):  # i.e. validate the exception was from an API call
        metadata = e.response.get("ResponseMetadata")
        if metadata:
            status_code = metadata.get("HTTPStatusCode", 400)
        logger.exception(e)
    elif hasattr(e, "http_status_code"):
        status_code = e.http_status_code
        logger.exception(e)
    else:
        error_msg = str(e)
        if error_msg in ["'requestContext'", "'pathParameters'", "'body'"]:
            e = f"Missing event parameter: {error_msg}"  # type: ignore [assignment]
        else:
            e = f"Bad Request: {error_msg}"  # type: ignore [assignment]
        logger.exception(e)
    return generate_html_response(status_code, e)  # type: ignore [arg-type]


def get_id_token(event: dict) -> str:
    """Return token from event request headers.

    Extracts bearer token from authorization header in lambda event.
    """
    auth_header = None

    if "authorization" in event["headers"]:
        auth_header = event["headers"]["authorization"]
    elif "Authorization" in event["headers"]:
        auth_header = event["headers"]["Authorization"]
    else:
        raise ValueError("Missing authorization token.")

    # remove bearer token prefix if present
    return str(auth_header).removeprefix("Bearer ").removeprefix("bearer ").strip()


_cert_file = None


@cache
def get_cert_path(iam_client: Any) -> Union[str, bool]:
    """
    Get cert path for IAM certs for SSL validation against LISA Serve endpoint.

    Returns the path to the certificate file for SSL verification, or True to use
    default verification if no certificate ARN is specified.
    """
    global _cert_file

    cert_arn = os.environ.get("RESTAPI_SSL_CERT_ARN")
    if not cert_arn:
        logger.info("No SSL certificate ARN specified, using default verification")
        return True
    # For ACM certificates, use default verification since they are trusted AWS certificates
    elif ":acm:" in cert_arn:
        logger.info("ACM certificate detected, using default SSL verification")
        return True

    try:
        # Clean up previous cert file if it exists
        if _cert_file and os.path.exists(_cert_file.name):
            try:
                os.unlink(_cert_file.name)
            except Exception as e:
                logger.warning(f"Failed to clean up previous cert file: {e}")

        # Get the certificate name from the ARN
        cert_name = cert_arn.split("/")[1]
        logger.info(f"Retrieving certificate '{cert_name}' from IAM")

        # Get the certificate from IAM
        rest_api_cert = iam_client.get_server_certificate(ServerCertificateName=cert_name)
        cert_body = rest_api_cert["ServerCertificate"]["CertificateBody"]

        # Create a new temporary file
        _cert_file = tempfile.NamedTemporaryFile(delete=False)
        _cert_file.write(cert_body.encode("utf-8"))
        _cert_file.flush()

        logger.info(f"Certificate saved to temporary file: {_cert_file.name}")
        return _cert_file.name

    except Exception as e:
        logger.error(f"Failed to get certificate from IAM: {e}", exc_info=True)
        # If we fail to get the cert, return True to fall back to default verification
        return True


@cache
def get_rest_api_container_endpoint() -> str:
    """Get REST API container base URI from SSM Parameter Store."""
    lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
    lisa_api_endpoint = lisa_api_param_response["Parameter"]["Value"]
    return f"{lisa_api_endpoint}/{os.environ['REST_API_VERSION']}/serve"


def get_username(event: dict) -> str:
    """Get the username from the event."""
    username: str = event.get("requestContext", {}).get("authorizer", {}).get("username", "system")
    return username


def get_session_id(event: dict) -> str:
    """Get the session ID from the event."""
    session_id: str = event.get("pathParameters", {}).get("sessionId")
    return session_id


def get_groups(event: Any) -> List[str]:
    """Get user groups from event."""
    groups: List[str] = json.loads(event.get("requestContext", {}).get("authorizer", {}).get("groups", "[]"))
    return groups


def get_principal_id(event: Any) -> str:
    """Get principal from event."""
    principal: str = event.get("requestContext", {}).get("authorizer", {}).get("principal", "")
    return principal


def merge_fields(source: dict, target: dict, fields: list[str]) -> dict:
    """
    Merge specified fields from source dictionary to target dictionary.
    Supports both top-level and nested fields using dot notation.

    Args:
        source: Source dictionary to copy fields from
        target: Target dictionary to copy fields into
        fields: List of field names, can use dot notation for nested fields

    Returns:
        Updated target dictionary
    """

    def get_nested_value(obj: dict[str, Any], path: list[str]) -> Any:
        current: Any = obj
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

    def set_nested_value(obj: dict, path: list[str], value: Any) -> None:
        current = obj
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        if value is not None:
            current[path[-1]] = value

    for field in fields:
        if "." in field:
            # Handle nested fields
            keys = field.split(".")
            value = get_nested_value(source, keys)
            if value is not None:
                set_nested_value(target, keys, value)
        else:
            # Handle top-level fields
            if field in source:
                target[field] = source[field]

    return target


def _get_lambda_role_arn() -> str:
    """Get the ARN of the Lambda execution role.

    Returns
    -------
    str
        The full ARN of the Lambda execution role
    """
    sts = boto3.client("sts", region_name=os.environ["AWS_REGION"])
    identity = sts.get_caller_identity()
    return cast(str, identity["Arn"])  # This will include the role name


def get_lambda_role_name() -> str:
    """Extract the role name from the Lambda execution role ARN.

    Returns
    -------
    str
        The name of the Lambda execution role without the full ARN
    """
    arn = _get_lambda_role_arn()
    parts = arn.split(":assumed-role/")[1].split("/")
    return parts[0]  # This is the role name


def get_item(response: Any) -> Any:
    items = response.get("Items", [])
    return items[0] if items else None


def user_has_group_access(user_groups: List[str], allowed_groups: List[str]) -> bool:
    """
    Check if user has access based on group membership.

    Args:
        user_groups: List of groups the user belongs to
        allowed_groups: List of groups allowed to access the resource

    Returns:
        True if user has access (either no restrictions or user has required group)
    """
    # Public resource (no group restrictions)
    if not allowed_groups:
        return True

    # Check if user has at least one matching group
    return len(set(user_groups).intersection(set(allowed_groups))) > 0
