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

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from utilities.exceptions import ForbiddenException, HTTPException, NotFoundException, UnauthorizedException
from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware
from utilities.fastapi_middleware.exception_handlers import generic_exception_handler
from utilities.fastapi_middleware.input_validation_middleware import InputValidationMiddleware
from utilities.fastapi_middleware.request_logging_middleware import RequestLoggingMiddleware
from utilities.fastapi_middleware.security_headers_middleware import SecurityHeadersMiddleware


def create_fastapi_app() -> FastAPI:
    """
    Create a FastAPI application with standard LISA configuration.

    This factory function creates a FastAPI app with:
    - Standard FastAPI settings (redirect_slashes, lifespan, docs)
    - Input validation middleware (null bytes, request size, HTTP methods)
    - AWS API Gateway middleware (extracts Lambda event context)
    - Request logging middleware (audit trail with sanitized data)
    - Security headers middleware (HSTS, X-Frame-Options, etc.)
    - CORS middleware with permissive settings
    - Request validation exception handler (422 errors)
    - Generic exception handler (500 errors)

    Middleware execution order (IMPORTANT):
    1. InputValidationMiddleware - Validates input FIRST (security)
    2. AWSAPIGatewayMiddleware - Extracts AWS event context
    3. RequestLoggingMiddleware - Logs requests with sanitized data
    4. SecurityHeadersMiddleware - Adds security headers to responses
    5. CORSMiddleware - Handles CORS (last middleware)

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

    # Add middleware in reverse order (last added = first executed)
    # Middleware execution order: InputValidation -> AWSAPIGateway -> RequestLogging -> SecurityHeaders -> CORS

    # CORS middleware (executed last, added first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers middleware (adds HSTS, X-Frame-Options, etc.)
    app.add_middleware(SecurityHeadersMiddleware)

    # Request logging middleware (logs all requests with sanitized data)
    app.add_middleware(RequestLoggingMiddleware)

    # AWS API Gateway middleware (extracts Lambda event context)
    app.add_middleware(AWSAPIGatewayMiddleware)

    # Input validation middleware (must be executed first for security)
    app.add_middleware(InputValidationMiddleware)

    # Register standard exception handlers

    # HTTP exceptions (401, 403, 404, etc.)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle custom HTTP exceptions and translate to appropriate status codes."""
        return JSONResponse(status_code=exc.http_status_code, content={"message": exc.message})

    # Convenience aliases for specific HTTP exceptions (for direct import in tests)
    @app.exception_handler(UnauthorizedException)
    async def unauthorized_handler(request: Request, exc: UnauthorizedException) -> JSONResponse:
        """Handle unauthorized exceptions and translate to a 401 error."""
        return JSONResponse(status_code=401, content={"message": exc.message})

    @app.exception_handler(ForbiddenException)
    async def forbidden_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
        """Handle forbidden exceptions and translate to a 403 error."""
        return JSONResponse(status_code=403, content={"message": exc.message})

    @app.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
        """Handle not found exceptions and translate to a 404 error."""
        return JSONResponse(status_code=404, content={"message": exc.message})

    # Request validation errors (422)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle exception when request fails validation and translate to a 422 error."""
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors()), "type": "RequestValidationError"},
        )

    # Generic exception handler (500) - must be registered last
    @app.exception_handler(Exception)
    async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions - delegates to common handler."""
        return await generic_exception_handler(request, exc)

    return app
