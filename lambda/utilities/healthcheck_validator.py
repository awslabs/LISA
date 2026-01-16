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

"""Validator for ECS healthcheck command format."""
from typing import Union


def validate_healthcheck_command(command: str | list[str]) -> None:
    """
    Validate ECS healthcheck command format.

    This validation ensures the command format is compatible with ECS requirements
    to prevent deployment failures. It does NOT restrict command content - admins
    are trusted to configure their containers appropriately.

    Args:
        command: Healthcheck command as string or array

    Raises:
        ValueError: If command format is invalid for ECS

    Examples:
        Valid formats:
        - "curl -f http://localhost:8080/health"
        - ["CMD-SHELL", "curl -f http://localhost:8080/health"]
        - ["CMD", "curl", "-f", "http://localhost:8080/health"]

        Invalid formats:
        - "" (empty string)
        - [] (empty array)
        - ["curl", "-f", "..."] (missing CMD/CMD-SHELL prefix)
    """
    # Check if command is None
    if command is None:
        raise ValueError("Healthcheck command cannot be None")

    # Check if command is string
    if isinstance(command, str):
        if not command.strip():
            raise ValueError("Healthcheck command cannot be an empty string")
        # String format is valid - ECS converts to CMD-SHELL
        return

    # Check if command is list
    if isinstance(command, list):
        if len(command) == 0:
            raise ValueError("Healthcheck command array cannot be empty")

        # Check first element is CMD or CMD-SHELL
        if command[0] not in ["CMD", "CMD-SHELL"]:
            raise ValueError(
                f"Healthcheck array must start with 'CMD' or 'CMD-SHELL', got: '{command[0]}'. "
                "Example: ['CMD-SHELL', 'curl -f http://localhost:8080/health']"
            )

        # Check there's at least one command after the prefix
        if len(command) < 2:
            raise ValueError(
                f"Healthcheck array must contain a command after '{command[0]}'. "
                "Example: ['CMD-SHELL', 'curl -f http://localhost:8080/health']"
            )

        # Check command part is not empty
        if isinstance(command[1], str) and not command[1].strip():
            raise ValueError("Healthcheck command cannot be empty after CMD/CMD-SHELL prefix")

        return

    # Invalid type
    raise ValueError(
        f"Healthcheck command must be a string or array, got: {type(command).__name__}. "
        "Example: ['CMD-SHELL', 'curl -f http://localhost:8080/health']"
    )
