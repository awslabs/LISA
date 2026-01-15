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

"""Unit tests for dict_helpers module."""

<<<<<<< HEAD
=======
import pytest

>>>>>>> 4e53cd7f (Added input validation, security headers, and logging to FastAPI lambdas and apiWrappers)
from utilities.dict_helpers import get_item, get_property_path, merge_fields


class TestMergeFields:
    """Test merge_fields function."""

    def test_merge_top_level_fields(self):
        """Test merge_fields with top-level fields."""
        source = {"field1": "value1", "field2": "value2", "field3": "value3"}
        target = {"existing": "data"}
        fields = ["field1", "field2"]

        result = merge_fields(source, target, fields)

        assert result["field1"] == "value1"
        assert result["field2"] == "value2"
        assert "field3" not in result
        assert result["existing"] == "data"

    def test_merge_nested_fields(self):
        """Test merge_fields with nested fields using dot notation."""
        source = {"user": {"profile": {"name": "John", "age": 30}, "email": "john@example.com"}}
        target = {"id": "123"}
        fields = ["user.profile.name", "user.email"]

        result = merge_fields(source, target, fields)

        assert result["user"]["profile"]["name"] == "John"
        assert result["user"]["email"] == "john@example.com"
        assert "age" not in result.get("user", {}).get("profile", {})
        assert result["id"] == "123"

    def test_merge_missing_source_field(self):
        """Test merge_fields when source field doesn't exist."""
        source = {"field1": "value1"}
        target = {"existing": "data"}
        fields = ["field1", "field2", "field3"]

        result = merge_fields(source, target, fields)

        assert result["field1"] == "value1"
        assert "field2" not in result
        assert "field3" not in result
        assert result["existing"] == "data"

    def test_merge_nested_missing_field(self):
        """Test merge_fields with missing nested fields."""
        source = {"user": {"name": "John"}}
        target = {}
        fields = ["user.profile.age"]

        result = merge_fields(source, target, fields)

        # Should not create nested structure if source doesn't have it
        assert result == {}

    def test_merge_mixed_fields(self):
        """Test merge_fields with mix of top-level and nested fields."""
        source = {"name": "John", "address": {"city": "Seattle", "state": "WA"}, "age": 30}
        target = {}
        fields = ["name", "address.city", "age"]

        result = merge_fields(source, target, fields)

        assert result["name"] == "John"
        assert result["address"]["city"] == "Seattle"
        assert "state" not in result["address"]
        assert result["age"] == 30

    def test_merge_overwrites_existing_fields(self):
        """Test merge_fields overwrites existing fields in target."""
        source = {"field1": "new_value"}
        target = {"field1": "old_value", "field2": "keep"}
        fields = ["field1"]

        result = merge_fields(source, target, fields)

        assert result["field1"] == "new_value"
        assert result["field2"] == "keep"

    def test_merge_with_none_values(self):
        """Test merge_fields handles None values."""
        source = {"field1": None, "field2": "value"}
        target = {}
        fields = ["field1", "field2"]

        result = merge_fields(source, target, fields)

        # Top-level None values ARE merged
        assert result["field1"] is None
        assert result["field2"] == "value"

    def test_merge_empty_fields_list(self):
        """Test merge_fields with empty fields list."""
        source = {"field1": "value1"}
        target = {"existing": "data"}
        fields = []

        result = merge_fields(source, target, fields)

        assert result == {"existing": "data"}


class TestGetPropertyPath:
    """Test get_property_path function."""

    def test_get_simple_property(self):
        """Test get_property_path with simple property."""
        data = {"name": "John", "age": 30}

        result = get_property_path(data, "name")

        assert result == "John"

    def test_get_nested_property(self):
        """Test get_property_path with nested property."""
        data = {"user": {"profile": {"name": "John", "age": 30}, "email": "john@example.com"}}

        result = get_property_path(data, "user.profile.name")

        assert result == "John"

    def test_get_deeply_nested_property(self):
        """Test get_property_path with deeply nested property."""
        data = {"level1": {"level2": {"level3": {"level4": "value"}}}}

        result = get_property_path(data, "level1.level2.level3.level4")

        assert result == "value"

    def test_returns_none_for_missing_property(self):
        """Test get_property_path returns None for missing property."""
        data = {"name": "John"}

        result = get_property_path(data, "age")

        assert result is None

    def test_returns_none_for_missing_nested_property(self):
        """Test get_property_path returns None for missing nested property."""
        data = {"user": {"name": "John"}}

        result = get_property_path(data, "user.profile.age")

        assert result is None

    def test_handles_empty_path(self):
        """Test get_property_path with empty path."""
        data = {"name": "John"}

        result = get_property_path(data, "")

        # Empty path returns None (no valid property to access)
        assert result is None

    def test_handles_list_values(self):
        """Test get_property_path with list values."""
        data = {"users": [{"name": "John"}, {"name": "Jane"}]}

        result = get_property_path(data, "users")

        assert result == [{"name": "John"}, {"name": "Jane"}]

    def test_handles_numeric_values(self):
        """Test get_property_path with numeric values."""
        data = {"count": 42, "price": 19.99}

        assert get_property_path(data, "count") == 42
        assert get_property_path(data, "price") == 19.99


class TestGetItem:
    """Test get_item function."""

    def test_returns_first_item(self):
        """Test get_item returns first item from DynamoDB response."""
        response = {"Items": [{"id": "1", "name": "First"}, {"id": "2", "name": "Second"}]}

        result = get_item(response)

        assert result == {"id": "1", "name": "First"}

    def test_returns_none_for_empty_items(self):
        """Test get_item returns None when Items list is empty."""
        response = {"Items": []}

        result = get_item(response)

        assert result is None

    def test_returns_none_for_missing_items_key(self):
        """Test get_item returns None when Items key is missing."""
        response = {"Count": 0}

        result = get_item(response)

        assert result is None

    def test_handles_single_item(self):
        """Test get_item with single item in response."""
        response = {"Items": [{"id": "123", "data": "value"}]}

        result = get_item(response)

        assert result == {"id": "123", "data": "value"}

    def test_ignores_additional_items(self):
        """Test get_item only returns first item, ignoring others."""
        response = {"Items": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}

        result = get_item(response)

        assert result == {"id": "1"}
