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

"""ASGI middleware to prevent StreamingResponse from seeing a second http.request.

When BaseHTTPMiddleware (or similar) is in the chain, StreamingResponse.listen_for_disconnect
calls receive() and can get a second http.request from the ASGI server, causing:
  RuntimeError: Unexpected message received: http.request

This middleware consumes the request body once at the ASGI layer and passes a receive
that replays the body once. For streaming requests (body has "stream": true), subsequent
calls return http.disconnect so the app never sees a second http.request. For
non-streaming requests, subsequent calls pass through to the real receive() so the
framework does not think the client disconnected and close the stream before sending
the response (which caused "No response returned").
"""

import json

from starlette.types import ASGIApp, Receive, Scope, Send


class StreamingSafeMiddleware:
    """Pure ASGI middleware that buffers the request body and provides a safe receive."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Consume the full request body so we can replay it once.
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                await self.app(scope, receive, send)
                return
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", True):
                    break

        # Only fake disconnect after first call for streaming; otherwise pass through
        # so BaseHTTPMiddleware does not close the stream before the response is sent.
        is_streaming = False
        if body and scope.get("method") in ("POST", "PUT", "PATCH"):
            try:
                params = json.loads(body)
                is_streaming = params.get("stream", False) is True
            except (json.JSONDecodeError, TypeError):
                pass

        first_call = [True]

        async def safe_receive() -> dict:
            if first_call[0]:
                first_call[0] = False
                return {"type": "http.request", "body": body, "more_body": False}
            if is_streaming:
                # Avoid second http.request for StreamingResponse.listen_for_disconnect.
                return {"type": "http.disconnect"}
            # Non-streaming: pass through so the framework sees real disconnect only
            # when the client disconnects (avoids "No response returned").
            return await receive()

        await self.app(scope, safe_receive, send)
