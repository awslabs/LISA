#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_user_has_access_admin():
    """Test user has access as admin"""
    from utilities.access_control_helpers import user_has_access

    result = user_has_access(
        username="admin",
        user_groups=["group1"],
        is_admin=True,
        allowed_groups=["group2"],
        owner="other",
        is_private=False,
    )
    
    assert result is True


def test_user_has_access_owner():
    """Test user has access as owner"""
    from utilities.access_control_helpers import user_has_access

    result = user_has_access(
        username="user1",
        user_groups=["group1"],
        is_admin=False,
        allowed_groups=["group2"],
        owner="user1",
        is_private=True,
    )
    
    assert result is True


def test_user_has_access_group():
    """Test user has access via group"""
    from utilities.access_control_helpers import user_has_access

    result = user_has_access(
        username="user1",
        user_groups=["group1", "group2"],
        is_admin=False,
        allowed_groups=["group2"],
        owner="other",
        is_private=False,
    )
    
    assert result is True


def test_user_no_access():
    """Test user has no access"""
    from utilities.access_control_helpers import user_has_access

    result = user_has_access(
        username="user1",
        user_groups=["group1"],
        is_admin=False,
        allowed_groups=["group2"],
        owner="other",
        is_private=False,
    )
    
    assert result is False


def test_validate_access_allowed():
    """Test validate access allowed"""
    from utilities.access_control_helpers import validate_access

    # Should not raise exception
    validate_access(
        username="admin",
        user_groups=["group1"],
        is_admin=True,
        allowed_groups=["group2"],
        owner="other",
        is_private=False,
        resource_type="collection",
        resource_id="test",
    )


def test_validate_access_denied():
    """Test validate access denied"""
    from utilities.access_control_helpers import validate_access
    from utilities.validation import ValidationError

    with pytest.raises(ValidationError, match="Permission denied"):
        validate_access(
            username="user1",
            user_groups=["group1"],
            is_admin=False,
            allowed_groups=["group2"],
            owner="other",
            is_private=False,
            resource_type="collection",
            resource_id="test",
        )


def test_check_group_access():
    """Test check group access"""
    from utilities.access_control_helpers import check_group_access

    result = check_group_access(["group1", "group2"], ["group2", "group3"])
    assert result is True

    result = check_group_access(["group1"], ["group2"])
    assert result is False


def test_is_owner():
    """Test is owner check"""
    from utilities.access_control_helpers import is_owner

    result = is_owner("user1", "user1")
    assert result is True

    result = is_owner("user1", "user2")
    assert result is False
