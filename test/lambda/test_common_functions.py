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