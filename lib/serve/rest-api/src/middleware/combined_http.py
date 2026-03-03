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

"""Single BaseHTTPMiddleware dispatch that chains security, validation, process, and auth.

Using one BaseHTTPMiddleware instead of four (@app.middleware("http") adds one per
decorator) avoids stacking multiple layers that cause "No response returned" and
"Unexpected message received: http.request" with StreamingResponse.
"""

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from .auth_middleware import auth_middleware
from .input_validation import validate_input_middleware
from .request_middleware import process_request_middleware
from .security_middleware import security_middleware


async def combined_http_dispatch(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Run security -> process_request -> validate_input -> auth -> route in one layer."""

    async def call_next_after_auth(req: Request) -> Response:
        return await auth_middleware(req, call_next)

    async def call_next_after_validate(req: Request) -> Response:
        return await validate_input_middleware(req, call_next_after_auth)

    async def call_next_after_process(req: Request) -> Response:
        return await process_request_middleware(req, call_next_after_validate)

    return await security_middleware(request, call_next_after_process)
