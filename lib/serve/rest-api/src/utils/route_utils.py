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

"""Shared route utilities for API path matching and validation."""

import fnmatch

# The following is an allowlist of OpenAI routes that users would not need elevated permissions to invoke. This is so
# that we may assume anything *not* in this allowlist is an admin operation that requires greater LiteLLM permissions.
# Assume that anything not within these routes requires admin permissions, which would only come from the LISA model
# management API.
OPENAI_ROUTES = (
    # List models
    "models",
    "v1/models",
    # Model Info
    "model/info",
    "v1/model/info",
    # Text completions
    "chat/completions",
    "v1/chat/completions",
    "completions",
    "v1/completions",
    # Embeddings
    "embeddings",
    "v1/embeddings",
    # Create images
    "images/generations",
    "v1/images/generations",
    "images/edits",
    "v1/images/edits",
    # Audio routes
    "audio/speech",
    "v1/audio/speech",
    "audio/transcriptions",
    "v1/audio/transcriptions",
    # Video routes (using wildcards for IDs)
    "videos",
    "v1/videos",
    "videos/*",
    "v1/videos/*",
    "videos/*/content",
    "v1/videos/*/content",
    "videos/*/remix",
    "v1/videos/*/remix",
    # Health check routes
    "health",
    "health/readiness",
    "health/liveliness",
    # MCP
    "mcp/enabled",
    "mcp/tools/list",
    "mcp/tools/call",
    "v1/mcp/server",
)

# LISA-specific routes that don't require admin access
# These are metadata and informational endpoints
LISA_PUBLIC_ROUTES = (
    "models/metadata/instances",
    "models/metadata/*",
)

# Specific routes for anthropic (Claude Code compatibility)
# LiteLLM's request/response format: https://litellm-api.up.railway.app/#/
ANTHROPIC_ROUTES = (
    # Anthropic Messages API
    "v1/messages",
    "v1/messages/count_tokens",
    # Anthropic Messages API with prefix
    "anthropic/v1/messages",
    "anthropic/v1/messages/count_tokens",
)

CHAT_ROUTES = (
    "chat/completions",
    "v1/chat/completions",
    "v1/messages",
    "anthropic/v1/messages",
)


def is_openai_route(api_path: str) -> bool:
    """Check if the given API path is an OpenAI-compatible route.

    This function checks both exact matches and wildcard patterns (for video routes).

    Args:
        api_path: The API path to check (without leading slash)

    Returns:
        True if the path matches an OpenAI route, False otherwise
    """
    # First check for exact matches (most common case)
    if api_path in OPENAI_ROUTES:
        return True

    # Only check wildcard patterns if the path contains "video" (since only video routes have wildcards)
    # This avoids expensive pattern matching for non-video routes
    if "video" not in api_path:
        return False

    wildcard_patterns = [pattern for pattern in OPENAI_ROUTES if "*" in pattern]
    wildcard_patterns.sort(key=len, reverse=True)

    for route_pattern in wildcard_patterns:
        if fnmatch.fnmatch(api_path, route_pattern):
            # For patterns like "videos/*" (not "videos/*/something"), ensure we don't match
            # paths with additional segments (e.g., "videos/123/content" should not match "videos/*")
            if route_pattern.endswith("/*") and not route_pattern.endswith("/*/"):
                pattern_segments = route_pattern.count("/")
                path_segments = api_path.count("/")
                if path_segments != pattern_segments:
                    continue
            return True

    return False


def is_lisa_public_route(api_path: str) -> bool:
    """Check if the given API path is a LISA public route.

    LISA public routes are metadata and informational endpoints that don't require admin access.

    Args:
        api_path: The API path to check (without leading slash)

    Returns:
        True if the path matches a LISA public route, False otherwise
    """
    # Check exact matches first
    if api_path in LISA_PUBLIC_ROUTES:
        return True

    # Check wildcard patterns
    wildcard_patterns = [pattern for pattern in LISA_PUBLIC_ROUTES if "*" in pattern]
    for route_pattern in wildcard_patterns:
        if fnmatch.fnmatch(api_path, route_pattern):
            return True

    return False


def is_anthropic_route(api_path: str) -> bool:
    """Check if the given API path is an Anthropic-compatible route.

    Args:
        api_path: The API path to check (without leading slash)

    Returns:
        True if the path matches an Anthropic route, False otherwise
    """
    return api_path in ANTHROPIC_ROUTES


def is_openai_or_anthropic_route(api_path: str) -> bool:
    """Check if the given API path is an OpenAI, Anthropic, or LISA public route.

    These routes require authentication but authorization (admin vs non-admin) is handled
    by the endpoint itself.

    Args:
        api_path: The API path to check (with or without leading slash)

    Returns:
        True if the path matches an OpenAI, Anthropic, or LISA public route, False otherwise
    """
    # Remove leading slash for comparison
    api_path = api_path.lstrip("/")

    return is_openai_route(api_path) or is_anthropic_route(api_path) or is_lisa_public_route(api_path)


def is_chat_route(api_path: str) -> bool:
    """Check if the given API path is a chat completion route.

    Args:
        api_path: The API path to check (without leading slash)

    Returns:
        True if the path is a chat completion route, False otherwise
    """
    return api_path in CHAT_ROUTES
