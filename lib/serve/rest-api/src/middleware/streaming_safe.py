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
that returns the body once then only http.disconnect, so the app and StreamingResponse
never see a second http.request.
"""

from starlette.types import ASGIApp, Receive, Scope, Send


class StreamingSafeMiddleware:
    """Pure ASGI middleware that buffers the request body and provides a safe receive."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Consume the full request body so we can replay it once and then only return
        # http.disconnect (avoids "Unexpected message received: http.request" when
        # StreamingResponse calls receive() and a middleware above returns a second
        # http.request).
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

        first_call = [True]

        async def safe_receive() -> dict:
            if first_call[0]:
                first_call[0] = False
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, safe_receive, send)
