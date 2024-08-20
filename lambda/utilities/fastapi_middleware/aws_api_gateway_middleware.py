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

"""Middleware for FastAPI that dynamically sets the root_path for Lambdas proxied through APIGW."""

from starlette.middleware.base import ASGIApp, BaseHTTPMiddleware, Request, RequestResponseEndpoint, Response


class AWSAPIGatewayMiddleware(BaseHTTPMiddleware):
    """
    Handles the FastAPI path and root_path dynamically from the ASGI request data.

    Mangum injects the AWS event data which we can use to dynamically set the path
    and root_path.
    https://github.com/jordaneremieff/mangum/issues/147
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware."""
        super().__init__(app)
        self.app = app

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and call the next middleware."""
        root_path = request.scope["root_path"]
        if root_path:
            # Assume set correctly in this case
            self.app.root_path = root_path

        else:
            if "aws.event" in request.scope and "pathParameters" in request.scope["aws.event"]:
                stage = request.scope["aws.event"]["requestContext"]["stage"]
                # Check if stage is the default, if so, we don't need to do anything
                if stage != "$default":
                    # If stage is not $default, it means we are behind an APIGateway
                    # stage and we need to set the path and root_path values correctly

                    # For example if the stage is "dev", and the path is "/dev/users/123"
                    # the root_path should be "/dev" and the path should be "/users/123"

                    # AWS/APIGateway conveniently provides pathParameters.proxy
                    # which is the path after the stage_part. We can use this to
                    # set the path.

                    # Set root_path value to APIGateway stage in requestContext
                    stage_path = f"/{stage}"
                    self.app.root_path = stage_path
                    request.scope["root_path"] = stage_path

        response = await call_next(request)
        return response
