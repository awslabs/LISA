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
from functools import cache
from typing import Any, Callable, Dict, TypeVar, Union

import boto3
import create_env_variables  # noqa type: ignore
from botocore.config import Config

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
        The functiont to be wrapped.

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
        "body": json.dumps(response_body, default=str),
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
        auth_header = event["headers"]["authorization"].split(" ")
    elif "Authorization" in event["headers"]:
        auth_header = event["headers"]["Authorization"].split(" ")
    else:
        raise ValueError("Missing authorization token.")

    if len(auth_header) == 1:
        # secret management token won't be split into multiple segments
        return str(auth_header[0])
    else:
        # Bearer tokens will have the token in the second segment
        return str(auth_header[1])


@cache
def get_cert_path(iam_client: Any) -> Union[str, bool]:
    """
    Get cert path for IAM certs for SSL validation against LISA Serve endpoint.

    If no SSL Cert ARN is specified just default verify to true and the cert will need to be
    signed by a known CA. Assume cert is signed with known CA if coming from ACM.

    Note: this function is a copy of the same function in the lisa-sdk path. To avoid inflating the deployment size of
    the Lambda functions, this function was copied here instead of including the entire lisa-sdk path.
    """
    cert_arn = os.environ.get("RESTAPI_SSL_CERT_ARN", "")
    if not cert_arn or cert_arn.split(":")[2] == "acm":
        return True

    # We have the arn, but we need the name which is the last part of the arn
    rest_api_cert = iam_client.get_server_certificate(ServerCertificateName=cert_arn.split("/")[1])
    cert_body = rest_api_cert["ServerCertificate"]["CertificateBody"]
    cert_file = tempfile.NamedTemporaryFile(delete=False)
    cert_file.write(cert_body.encode("utf-8"))
    rest_api_cert_path = cert_file.name

    return rest_api_cert_path


@cache
def get_rest_api_container_endpoint() -> str:
    """Get REST API container base URI from SSM Parameter Store."""
    lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
    lisa_api_endpoint = lisa_api_param_response["Parameter"]["Value"]
    return f"{lisa_api_endpoint}/{os.environ['REST_API_VERSION']}/serve"
