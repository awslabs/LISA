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

import json
import os
import sys
from decimal import Decimal

import pytest

from utilities.common_functions import get_property_path


def test_get_property_path(sample_jwt_data):
    """Test the get_property_path function."""
    # Test with simple property
    assert get_property_path(sample_jwt_data, "username") == "test-user"

    # Test with nested property
    assert get_property_path(sample_jwt_data, "nested.property") == "value"

    # Test with non-existent property
    assert get_property_path(sample_jwt_data, "nonexistent") is None

    # Test with non-existent nested property
    assert get_property_path(sample_jwt_data, "nested.nonexistent") is None

    # Test with non-existent parent
    assert get_property_path(sample_jwt_data, "nonexistent.property") is None


# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"


def test_decimal_encoder():
    """Test DecimalEncoder converts Decimal to float."""
    if "utilities.common_functions" in sys.modules:
        del sys.modules["utilities.common_functions"]

    from utilities.common_functions import DecimalEncoder

    encoder = DecimalEncoder()
    result = encoder.default(Decimal("10.5"))
    assert result == 10.5


def test_generate_html_response():
    """Test generate_html_response creates proper response."""
    if "utilities.common_functions" in sys.modules:
        del sys.modules["utilities.common_functions"]

    from utilities.common_functions import generate_html_response

    response = generate_html_response(200, {"message": "success"})

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"message": "success"}
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"


def test_get_username():
    """Test get_username extracts username from event."""
    if "utilities.common_functions" in sys.modules:
        del sys.modules["utilities.common_functions"]

    from utilities.common_functions import get_username

    event = {"requestContext": {"authorizer": {"username": "test-user"}}}

    username = get_username(event)
    assert username == "test-user"


def test_get_username_default():
    """Test get_username returns system when username missing."""
    if "utilities.common_functions" in sys.modules:
        del sys.modules["utilities.common_functions"]

    from utilities.common_functions import get_username

    event = {}

    username = get_username(event)
    assert username == "system"


def test_user_has_group_access_public():
    """Test user_has_group_access returns True for public resources."""
    if "utilities.common_functions" in sys.modules:
        del sys.modules["utilities.common_functions"]

    from utilities.common_functions import user_has_group_access

    result = user_has_group_access(["user"], [])
    assert result is True


def test_user_has_group_access_matching():
    """Test user_has_group_access returns True when user has matching group."""
    if "utilities.common_functions" in sys.modules:
        del sys.modules["utilities.common_functions"]

    from utilities.common_functions import user_has_group_access

    result = user_has_group_access(["admin", "user"], ["admin"])
    assert result is True


def test_merge_fields_top_level():
    """Test merge_fields with top-level fields."""
    if "utilities.common_functions" in sys.modules:
        del sys.modules["utilities.common_functions"]

    from utilities.common_functions import merge_fields

    source = {"name": "John", "age": 30, "city": "NYC"}
    target = {"country": "USA"}
    fields = ["name", "age"]

    result = merge_fields(source, target, fields)

    assert result["name"] == "John"
    assert result["age"] == 30
    assert result["country"] == "USA"
    assert "city" not in result


def test_validate_model_name_valid():
    """Test validate_model_name with valid model name."""
    if "utilities.validation" in sys.modules:
        del sys.modules["utilities.validation"]

    from utilities.validation import validate_model_name

    result = validate_model_name("valid-model-123")
    assert result is True


def test_validate_model_name_empty():
    """Test validate_model_name raises ValidationError for empty string."""
    if "utilities.validation" in sys.modules:
        del sys.modules["utilities.validation"]

    from utilities.validation import validate_model_name, ValidationError

    with pytest.raises(ValidationError):
        validate_model_name("")


def test_validate_instance_type_valid():
    """Test validate_instance_type with valid EC2 instance type."""
    if "utilities.validators" in sys.modules:
        del sys.modules["utilities.validators"]

    from utilities.validators import validate_instance_type

    result = validate_instance_type("t3.micro")
    assert result == "t3.micro"


def test_validate_all_fields_defined_true():
    """Test validate_all_fields_defined returns True when all fields are non-null."""
    if "utilities.validators" in sys.modules:
        del sys.modules["utilities.validators"]

    from utilities.validators import validate_all_fields_defined

    result = validate_all_fields_defined(["value1", "value2", "value3"])
    assert result is True


def test_validate_all_fields_defined_false():
    """Test validate_all_fields_defined returns False when any field is None."""
    if "utilities.validators" in sys.modules:
        del sys.modules["utilities.validators"]

    from utilities.validators import validate_all_fields_defined

    result = validate_all_fields_defined(["value1", None, "value3"])
    assert result is False
