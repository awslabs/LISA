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
from decimal import Decimal

# Set up mock AWS credentials first
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from utilities.encoders import convert_decimal


def test_convert_decimal_with_decimal():
    """Test convert_decimal with Decimal values"""
    # Test single Decimal
    result = convert_decimal(Decimal("123.45"))
    assert result == 123.45
    assert isinstance(result, float)

    # Test Decimal zero
    result = convert_decimal(Decimal("0"))
    assert result == 0.0
    assert isinstance(result, float)

    # Test negative Decimal
    result = convert_decimal(Decimal("-456.78"))
    assert result == -456.78
    assert isinstance(result, float)


def test_convert_decimal_with_dict():
    """Test convert_decimal with dictionary containing Decimals"""
    input_dict = {
        "price": Decimal("99.99"),
        "quantity": Decimal("5"),
        "name": "Product",
        "active": True,
        "nested": {"cost": Decimal("50.25"), "tax": Decimal("7.5")},
    }

    result = convert_decimal(input_dict)

    assert result["price"] == 99.99
    assert isinstance(result["price"], float)
    assert result["quantity"] == 5.0
    assert isinstance(result["quantity"], float)
    assert result["name"] == "Product"
    assert result["active"] is True
    assert result["nested"]["cost"] == 50.25
    assert isinstance(result["nested"]["cost"], float)
    assert result["nested"]["tax"] == 7.5
    assert isinstance(result["nested"]["tax"], float)


def test_convert_decimal_with_list():
    """Test convert_decimal with list containing Decimals"""
    input_list = [Decimal("10.5"), "string_value", 42, [Decimal("3.14"), "nested"], {"amount": Decimal("100.00")}]

    result = convert_decimal(input_list)

    assert result[0] == 10.5
    assert isinstance(result[0], float)
    assert result[1] == "string_value"
    assert result[2] == 42
    assert result[3][0] == 3.14
    assert isinstance(result[3][0], float)
    assert result[3][1] == "nested"
    assert result[4]["amount"] == 100.0
    assert isinstance(result[4]["amount"], float)


def test_convert_decimal_with_non_decimal_types():
    """Test convert_decimal with non-Decimal types (should pass through unchanged)"""
    # Test string
    result = convert_decimal("hello")
    assert result == "hello"

    # Test integer
    result = convert_decimal(42)
    assert result == 42

    # Test float
    result = convert_decimal(3.14)
    assert result == 3.14

    # Test boolean
    result = convert_decimal(True)
    assert result is True

    # Test None
    result = convert_decimal(None)
    assert result is None


def test_convert_decimal_with_empty_collections():
    """Test convert_decimal with empty dict and list"""
    # Test empty dict
    result = convert_decimal({})
    assert result == {}

    # Test empty list
    result = convert_decimal([])
    assert result == []


def test_convert_decimal_with_complex_nested_structure():
    """Test convert_decimal with deeply nested structure"""
    complex_data = {
        "users": [
            {
                "id": 1,
                "balance": Decimal("1000.50"),
                "transactions": [
                    {"amount": Decimal("50.25"), "type": "debit"},
                    {"amount": Decimal("100.75"), "type": "credit"},
                ],
                "metadata": {"scores": [Decimal("95.5"), Decimal("87.2")], "rating": Decimal("4.8")},
            }
        ],
        "totals": {"sum": Decimal("2000.00"), "average": Decimal("666.67")},
    }

    result = convert_decimal(complex_data)

    # Check user balance
    assert result["users"][0]["balance"] == 1000.50
    assert isinstance(result["users"][0]["balance"], float)

    # Check transaction amounts
    assert result["users"][0]["transactions"][0]["amount"] == 50.25
    assert isinstance(result["users"][0]["transactions"][0]["amount"], float)
    assert result["users"][0]["transactions"][1]["amount"] == 100.75
    assert isinstance(result["users"][0]["transactions"][1]["amount"], float)

    # Check metadata scores
    assert result["users"][0]["metadata"]["scores"][0] == 95.5
    assert isinstance(result["users"][0]["metadata"]["scores"][0], float)
    assert result["users"][0]["metadata"]["scores"][1] == 87.2
    assert isinstance(result["users"][0]["metadata"]["scores"][1], float)

    # Check metadata rating
    assert result["users"][0]["metadata"]["rating"] == 4.8
    assert isinstance(result["users"][0]["metadata"]["rating"], float)

    # Check totals
    assert result["totals"]["sum"] == 2000.0
    assert isinstance(result["totals"]["sum"], float)
    assert result["totals"]["average"] == 666.67
    assert isinstance(result["totals"]["average"], float)

    # Check non-Decimal values remain unchanged
    assert result["users"][0]["id"] == 1
    assert result["users"][0]["transactions"][0]["type"] == "debit"
    assert result["users"][0]["transactions"][1]["type"] == "credit"


def test_convert_decimal_with_mixed_types_in_list():
    """Test convert_decimal with list containing mixed types including nested structures"""
    mixed_list = [
        Decimal("123.45"),
        {"price": Decimal("99.99"), "name": "Item"},
        [Decimal("1.1"), Decimal("2.2"), "text"],
        "plain_string",
        42,
        None,
        True,
    ]

    result = convert_decimal(mixed_list)

    assert result[0] == 123.45
    assert isinstance(result[0], float)
    assert result[1]["price"] == 99.99
    assert isinstance(result[1]["price"], float)
    assert result[1]["name"] == "Item"
    assert result[2][0] == 1.1
    assert isinstance(result[2][0], float)
    assert result[2][1] == 2.2
    assert isinstance(result[2][1], float)
    assert result[2][2] == "text"
    assert result[3] == "plain_string"
    assert result[4] == 42
    assert result[5] is None
    assert result[6] is True


def test_convert_decimal_preserves_original_structure():
    """Test that convert_decimal preserves the original data structure"""
    original = {"level1": {"level2": {"level3": [{"value": Decimal("42.0")}, {"value": Decimal("84.0")}]}}}

    result = convert_decimal(original)

    # Check structure is preserved
    assert "level1" in result
    assert "level2" in result["level1"]
    assert "level3" in result["level1"]["level2"]
    assert len(result["level1"]["level2"]["level3"]) == 2

    # Check values are converted
    assert result["level1"]["level2"]["level3"][0]["value"] == 42.0
    assert isinstance(result["level1"]["level2"]["level3"][0]["value"], float)
    assert result["level1"]["level2"]["level3"][1]["value"] == 84.0
    assert isinstance(result["level1"]["level2"]["level3"][1]["value"], float)
