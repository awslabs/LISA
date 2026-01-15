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

"""Factory for creating FastAPI applications with standard LISA configuration."""

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware
from utilities.fastapi_middleware.exception_handlers import generic_exception_handler
from utilities.fastapi_middleware.input_validation_middleware import InputValidationMiddleware


def create_fastapi_app() -> FastAPI:
    """
    Create a FastAPI application with standard LISA configuration.

    This factory function creates a FastAPI app with:
    - Standard FastAPI settings (redirect_slashes, lifespan, docs)
    - Input validation middleware (must be first)
    - AWS API Gateway middleware
    - CORS middleware with permissive settings
    - Request validation exception handler (422 errors)
    - Generic exception handler (500 errors)

    Returns:
        FastAPI: Configured FastAPI application instance

    Example:
        >>> from utilities.fastapi_factory import create_fastapi_app
        >>> app = create_fastapi_app()
        >>> # Add domain-specific exception handlers
        >>> @app.exception_handler(MyCustomError)
        >>> async def my_handler(request, exc):
        >>>     return JSONResponse(status_code=404, content={"error": str(exc)})
    """
    # Create FastAPI app with standard settings
    app = FastAPI(
        redirect_slashes=False,
        lifespan="off",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Add input validation middleware (must be added before other middleware)
    app.add_middleware(InputValidationMiddleware)
    # Add AWS API Gateway middleware
    app.add_middleware(AWSAPIGatewayMiddleware)
    # Enable CORS with permissive settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standard exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError) -> JSONResponse:
        """Handle exception when request fails validation and translate to a 422 error."""
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors()), "type": "RequestValidationError"},
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedError) -> JSONResponse:
        """Handle unauthorized access attempts and translate to a 401 error."""
        return JSONResponse(status_code=401, content={"message": str(exc)})


    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        """Handle forbidden access attempts and translate to a 403 error."""
        return JSONResponse(status_code=403, content={"message": str(exc)})

    # Generic exception handler (500) - must be registered last
    @app.exception_handler(Exception)
    async def handle_generic_exception(request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions - delegates to common handler."""
        return await generic_exception_handler(request, exc)

    return app
