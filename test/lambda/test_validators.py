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


import os
import sys

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


def test_validate_instance_type_valid():
    """Test validate_instance_type with valid EC2 instance type."""
    from utilities.validation import validate_instance_type

    result = validate_instance_type("t3.micro")
    assert result == "t3.micro"


def test_validate_instance_type_invalid():
    """Test validate_instance_type with invalid instance type."""
    from utilities.validation import validate_instance_type

    with pytest.raises(ValueError, match="Invalid EC2 instance type"):
        validate_instance_type("invalid-type")


def test_validate_all_fields_defined_true():
    """Test validate_all_fields_defined returns True when all fields are non-null."""
    from utilities.validation import validate_all_fields_defined

    result = validate_all_fields_defined(["value1", "value2", "value3"])
    assert result is True


def test_validate_all_fields_defined_false():
    """Test validate_all_fields_defined returns False when any field is None."""
    from utilities.validation import validate_all_fields_defined

    result = validate_all_fields_defined(["value1", None, "value3"])
    assert result is False


def test_validate_all_fields_defined_empty():
    """Test validate_all_fields_defined returns True for empty list."""
    from utilities.validation import validate_all_fields_defined

    result = validate_all_fields_defined([])
    assert result is True


def test_validate_any_fields_defined_true():
    """Test validate_any_fields_defined returns True when at least one field is non-null."""
    from utilities.validation import validate_any_fields_defined

    result = validate_any_fields_defined([None, "value2", None])
    assert result is True


def test_validate_any_fields_defined_false():
    """Test validate_any_fields_defined returns False when all fields are None."""
    from utilities.validation import validate_any_fields_defined

    result = validate_any_fields_defined([None, None, None])
    assert result is False


def test_validate_any_fields_defined_empty():
    """Test validate_any_fields_defined returns False for empty list."""
    from utilities.validation import validate_any_fields_defined

    result = validate_any_fields_defined([])
    assert result is False
