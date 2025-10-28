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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from utilities.access_control import AccessDecision, BaseAccessControlPolicy, Permission, ResourceContext, UserContext


def test_access_decision_allowed():
    decision = AccessDecision(allowed=True, permission=Permission.READ, granting_groups=["group1"])
    assert decision.allowed
    assert decision.permission == Permission.READ
    assert "group1" in decision.granting_groups


def test_access_decision_denied():
    decision = AccessDecision(allowed=False, permission=Permission.WRITE, reason="No access")
    assert not decision.allowed
    assert decision.reason == "No access"


def test_user_context():
    user = UserContext(user_id="user1", groups=["group1", "group2"], is_admin=False)
    assert user.user_id == "user1"
    assert len(user.groups) == 2


def test_resource_context():
    resource = ResourceContext(
        resource_id="res1",
        resource_type="collection",
        allowed_groups=["group1"],
        owner_id="user1",
        is_private=True,
    )
    assert resource.resource_id == "res1"
    assert resource.is_private


def test_base_policy_check_group_access():
    class ConcretePolicy(BaseAccessControlPolicy):
        def get_resource_context(self, resource_id, **kwargs):
            return None

    policy = ConcretePolicy()

    # Test public resource
    decision = policy._check_group_access(["group1"], [], Permission.READ)
    assert decision.allowed

    # Test matching groups
    decision = policy._check_group_access(["group1"], ["group1", "group2"], Permission.READ)
    assert decision.allowed
    assert "group1" in decision.granting_groups

    # Test no matching groups
    decision = policy._check_group_access(["group3"], ["group1", "group2"], Permission.READ)
    assert not decision.allowed
