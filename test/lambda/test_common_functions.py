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