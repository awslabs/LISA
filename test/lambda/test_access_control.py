#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from utilities.access_control import (
    Permission,
    AccessDecision,
    UserContext,
    ResourceContext,
    BaseAccessControlPolicy,
    CachedAccessControlService,
)


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


def test_cached_service():
    policy = MagicMock(spec=BaseAccessControlPolicy)
    policy.check_access.return_value = AccessDecision(
        allowed=True, permission=Permission.READ, granting_groups=["group1"]
    )
    
    service = CachedAccessControlService(policy)
    user = UserContext(user_id="user1", groups=["group1"], is_admin=False)
    resource = ResourceContext(resource_id="res1", resource_type="test")
    
    decision1 = service.check_access(user, resource, Permission.READ)
    decision2 = service.check_access(user, resource, Permission.READ)
    
    assert decision1.allowed
    assert decision2.allowed
    assert policy.check_access.call_count == 1


def test_cached_service_clear_cache():
    policy = MagicMock(spec=BaseAccessControlPolicy)
    service = CachedAccessControlService(policy)
    
    service._cache["key1"] = AccessDecision(allowed=True, permission=Permission.READ)
    service.clear_cache()
    
    assert len(service._cache) == 0


def test_cached_service_clear_resource():
    policy = MagicMock(spec=BaseAccessControlPolicy)
    service = CachedAccessControlService(policy)
    
    service._cache["user1:res1:read"] = AccessDecision(allowed=True, permission=Permission.READ)
    service._cache["user2:res1:write"] = AccessDecision(allowed=True, permission=Permission.WRITE)
    service._cache["user1:res2:read"] = AccessDecision(allowed=True, permission=Permission.READ)
    
    service.clear_cache_for_resource("res1")
    
    assert "user1:res1:read" not in service._cache
    assert "user2:res1:write" not in service._cache
    assert "user1:res2:read" in service._cache
