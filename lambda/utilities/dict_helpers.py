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

"""Generic dictionary manipulation utilities."""

from typing import Any, Optional


def merge_fields(source: dict, target: dict, fields: list[str]) -> dict:
    """
    Merge specified fields from source dictionary to target dictionary.

    Supports both top-level and nested fields using dot notation.

    Parameters
    ----------
    source : dict
        Source dictionary to copy fields from.
    target : dict
        Target dictionary to copy fields into.
    fields : list[str]
        List of field names, can use dot notation for nested fields.

    Returns
    -------
    dict
        Updated target dictionary.

    Example
    -------
    >>> source = {"user": {"name": "John", "age": 30}, "status": "active"}
    >>> target = {"id": "123"}
    >>> merge_fields(source, target, ["user.name", "status"])
    {'id': '123', 'user': {'name': 'John'}, 'status': 'active'}
    """

    def get_nested_value(obj: dict[str, Any], path: list[str]) -> Any:
        """Get value from nested dictionary using path."""
        current: Any = obj
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

    def set_nested_value(obj: dict, path: list[str], value: Any) -> None:
        """Set value in nested dictionary using path."""
        current = obj
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        if value is not None:
            current[path[-1]] = value

    for field in fields:
        if "." in field:
            # Handle nested fields
            keys = field.split(".")
            value = get_nested_value(source, keys)
            if value is not None:
                set_nested_value(target, keys, value)
        else:
            # Handle top-level fields
            if field in source:
                target[field] = source[field]

    return target


def get_property_path(data: dict[str, Any], property_path: str) -> Optional[Any]:
    """
    Get value from nested dictionary using dot-notation path.

    Parameters
    ----------
    data : dict[str, Any]
        Dictionary to extract value from.
    property_path : str
        Dot-notation path to the property (e.g., "user.address.city").

    Returns
    -------
    Optional[Any]
        The value at the specified path, or None if path doesn't exist.

    Example
    -------
    >>> data = {"user": {"address": {"city": "Seattle"}}}
    >>> get_property_path(data, "user.address.city")
    'Seattle'
    >>> get_property_path(data, "user.phone")
    None
    """
    props = property_path.split(".")
    current_node = data
    for prop in props:
        if prop in current_node:
            current_node = current_node[prop]
        else:
            return None

    return current_node


def get_item(response: Any) -> Any:
    """
    Extract first item from DynamoDB query/scan response.

    Parameters
    ----------
    response : Any
        DynamoDB query or scan response.

    Returns
    -------
    Any
        First item from the response, or None if no items.

    Example
    -------
    >>> response = {"Items": [{"id": "123", "name": "John"}]}
    >>> get_item(response)
    {'id': '123', 'name': 'John'}
    """
    items = response.get("Items", [])
    return items[0] if items else None
