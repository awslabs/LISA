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

"""Unit tests for ECS healthcheck command validator."""
import pytest
from utilities.healthcheck_validator import validate_healthcheck_command


class TestValidHealthcheckFormats:
    """Test valid healthcheck command formats."""

    def test_valid_string_command(self):
        """Test that a non-empty string command is valid."""
        # Valid string format - ECS converts to CMD-SHELL
        validate_healthcheck_command("curl -f http://localhost:8080/health")
        # Should not raise any exception

    def test_valid_string_with_complex_command(self):
        """Test that complex string commands are valid."""
        validate_healthcheck_command("curl -f http://localhost:8080/health || exit 1")
        # Should not raise any exception

    def test_valid_cmd_shell_array(self):
        """Test that CMD-SHELL array format is valid."""
        validate_healthcheck_command(["CMD-SHELL", "curl -f http://localhost:8080/health"])
        # Should not raise any exception

    def test_valid_cmd_shell_array_with_complex_command(self):
        """Test that CMD-SHELL with complex shell command is valid."""
        validate_healthcheck_command(["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"])
        # Should not raise any exception

    def test_valid_cmd_array(self):
        """Test that CMD array format is valid."""
        validate_healthcheck_command(["CMD", "curl", "-f", "http://localhost:8080/health"])
        # Should not raise any exception

    def test_valid_cmd_array_single_argument(self):
        """Test that CMD array with single argument is valid."""
        validate_healthcheck_command(["CMD", "/healthcheck.sh"])
        # Should not raise any exception

    def test_valid_cmd_array_multiple_arguments(self):
        """Test that CMD array with multiple arguments is valid."""
        validate_healthcheck_command(["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080')"])
        # Should not raise any exception


class TestInvalidHealthcheckFormats:
    """Test invalid healthcheck command formats."""

    def test_none_command_raises_error(self):
        """Test that None command raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(None)

        assert "cannot be None" in str(exc_info.value)

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command("")

        assert "cannot be an empty string" in str(exc_info.value)

    def test_whitespace_only_string_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command("   ")

        assert "cannot be an empty string" in str(exc_info.value)

    def test_empty_array_raises_error(self):
        """Test that empty array raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command([])

        assert "array cannot be empty" in str(exc_info.value)

    def test_array_without_cmd_prefix_raises_error(self):
        """Test that array without CMD/CMD-SHELL prefix raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["curl", "-f", "http://localhost:8080/health"])

        error_message = str(exc_info.value)
        assert "must start with 'CMD' or 'CMD-SHELL'" in error_message
        assert "got: 'curl'" in error_message

    def test_array_with_invalid_prefix_raises_error(self):
        """Test that array with invalid prefix raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["SHELL", "curl -f http://localhost:8080/health"])

        error_message = str(exc_info.value)
        assert "must start with 'CMD' or 'CMD-SHELL'" in error_message
        assert "got: 'SHELL'" in error_message

    def test_array_with_only_cmd_prefix_raises_error(self):
        """Test that array with only CMD prefix and no command raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["CMD"])

        error_message = str(exc_info.value)
        assert "must contain a command after 'CMD'" in error_message

    def test_array_with_only_cmd_shell_prefix_raises_error(self):
        """Test that array with only CMD-SHELL prefix and no command raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["CMD-SHELL"])

        error_message = str(exc_info.value)
        assert "must contain a command after 'CMD-SHELL'" in error_message

    def test_array_with_empty_command_after_prefix_raises_error(self):
        """Test that array with empty command after prefix raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["CMD-SHELL", ""])

        assert "cannot be empty after CMD/CMD-SHELL prefix" in str(exc_info.value)

    def test_array_with_whitespace_command_after_prefix_raises_error(self):
        """Test that array with whitespace-only command after prefix raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["CMD-SHELL", "   "])

        assert "cannot be empty after CMD/CMD-SHELL prefix" in str(exc_info.value)

    def test_integer_command_raises_error(self):
        """Test that integer command raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(123)

        error_message = str(exc_info.value)
        assert "must be a string or array" in error_message
        assert "got: int" in error_message

    def test_dict_command_raises_error(self):
        """Test that dict command raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command({"command": "curl"})

        error_message = str(exc_info.value)
        assert "must be a string or array" in error_message
        assert "got: dict" in error_message

    def test_boolean_command_raises_error(self):
        """Test that boolean command raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(True)

        error_message = str(exc_info.value)
        assert "must be a string or array" in error_message
        assert "got: bool" in error_message


class TestErrorMessageHelpfulness:
    """Test that error messages provide helpful guidance."""

    def test_missing_prefix_error_includes_example(self):
        """Test that missing prefix error includes example format."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["curl", "http://localhost:8080"])

        error_message = str(exc_info.value)
        assert "Example:" in error_message
        assert "CMD-SHELL" in error_message
        assert "curl" in error_message

    def test_empty_array_after_prefix_error_includes_example(self):
        """Test that empty command error includes example format."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["CMD"])

        error_message = str(exc_info.value)
        assert "Example:" in error_message
        assert "CMD-SHELL" in error_message

    def test_wrong_type_error_includes_example(self):
        """Test that wrong type error includes example format."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(123)

        error_message = str(exc_info.value)
        assert "Example:" in error_message
        assert "CMD-SHELL" in error_message

    def test_error_messages_mention_both_cmd_and_cmd_shell(self):
        """Test that error messages mention both valid prefixes."""
        with pytest.raises(ValueError) as exc_info:
            validate_healthcheck_command(["INVALID", "command"])

        error_message = str(exc_info.value)
        assert "CMD" in error_message
        assert "CMD-SHELL" in error_message
