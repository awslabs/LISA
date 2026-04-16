"""Minimal FastAPI app to locally validate rate limiting middleware end-to-end."""
import os
import sys
from pathlib import Path

# Set env vars BEFORE importing the middleware (it reads them at import time)
os.environ["RATE_LIMIT_RPM"] = "5"
os.environ["RATE_LIMIT_BURST"] = "2"
os.environ["RATE_LIMIT_ENABLED"] = "true"

# Add the REST API source to the path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from middleware.rate_limit_middleware import rate_limit_middleware

app = FastAPI()


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)


@app.middleware("http")
async def _fake_auth(request: Request, call_next):
    """Simulate auth middleware setting request.state for an API token user."""
    request.state.authenticated = True
    request.state.api_token_info = {"tokenUUID": "test-token-uuid", "username": "test-user"}
    return await call_next(request)


@app.post("/v2/serve/chat/completions")
async def chat_completions():
    return JSONResponse({"message": "ok"})


@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy"})
