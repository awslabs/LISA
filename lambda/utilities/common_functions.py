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

"""
Common helper functions for RAG Lambdas.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from the specific utility modules:

- lambda_decorators: api_wrapper, authorization_wrapper
- response_builder: generate_html_response, generate_exception_response, DecimalEncoder
- event_parser: get_session_id, get_principal_id, get_bearer_token, get_id_token
- aws_helpers: get_cert_path, get_rest_api_container_endpoint, get_lambda_role_name, get_account_and_partition
- dict_helpers: merge_fields, get_property_path, get_item
"""
import logging
from typing import Any, TypeVar
from collections.abc import Callable

# Re-export from organized modules for backward compatibility
from utilities.aws_helpers import (
    get_account_and_partition,
    get_cert_path,
    get_lambda_role_name,
    get_rest_api_container_endpoint,
    retry_config,
    ssm_client,
)
from utilities.dict_helpers import get_item, get_property_path, merge_fields
from utilities.event_parser import get_bearer_token, get_id_token, get_principal_id, get_session_id
from utilities.lambda_decorators import api_wrapper, authorization_wrapper, ctx_context
from utilities.response_builder import DecimalEncoder, generate_exception_response, generate_html_response

from . import create_env_variables  # noqa type: ignore

F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger(__name__)
logging_configured = False


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


# Export all public functions for backward compatibility
__all__ = [
    # Lambda decorators
    "api_wrapper",
    "authorization_wrapper",
    "ctx_context",
    # Response builders
    "generate_html_response",
    "generate_exception_response",
    "DecimalEncoder",
    # Event parsers
    "get_session_id",
    "get_principal_id",
    "get_bearer_token",
    "get_id_token",
    # AWS helpers
    "get_cert_path",
    "get_rest_api_container_endpoint",
    "get_lambda_role_name",
    "get_account_and_partition",
    "retry_config",
    "ssm_client",
    # Dict helpers
    "merge_fields",
    "get_property_path",
    "get_item",
    # Logging
    "LambdaContextFilter",
    "setup_root_logging",
]
