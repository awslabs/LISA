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

#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


def test_user_has_access_admin():
    from utilities.access_control_helpers import user_has_access

    assert user_has_access("user1", [], True, [], "owner1", True) is True


def test_user_has_access_owner():
    from utilities.access_control_helpers import user_has_access

    assert user_has_access("user1", [], False, [], "user1", True) is True


def test_user_has_access_group():
    from utilities.access_control_helpers import user_has_access

    assert user_has_access("user1", ["group1"], False, ["group1"], "owner1", False) is True


def test_user_has_access_denied():
    from utilities.access_control_helpers import user_has_access

    assert user_has_access("user1", [], False, [], "owner1", True) is False


def test_validate_access():
    from utilities.access_control_helpers import validate_access, ValidationError

    with pytest.raises(ValidationError):
        validate_access("user1", [], False, [], "owner1", True, "collection", "col1")


def test_check_group_access():
    from utilities.access_control_helpers import check_group_access

    assert check_group_access(["group1"], ["group1", "group2"]) is True
    assert check_group_access(["group3"], ["group1", "group2"]) is False


def test_is_owner():
    from utilities.access_control_helpers import is_owner

    assert is_owner("user1", "user1") is True
    assert is_owner("user1", "user2") is False
