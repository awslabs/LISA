#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def setup_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_get_username(setup_env):
    from utilities.common_functions import get_username
    
    event = {"requestContext": {"authorizer": {"username": "testuser"}}}
    assert get_username(event) == "testuser"


def test_get_username_default(setup_env):
    from utilities.common_functions import get_username
    
    event = {}
    assert get_username(event) == "system"


def test_get_groups(setup_env):
    import json
    from utilities.common_functions import get_groups
    
    event = {"requestContext": {"authorizer": {"groups": json.dumps(["group1"])}}}
    groups = get_groups(event)
    assert len(groups) >= 1


def test_get_principal_id(setup_env):
    from utilities.common_functions import get_principal_id
    
    event = {"requestContext": {"authorizer": {"principal": "principal123"}}}
    assert get_principal_id(event) == "principal123"


def test_user_has_group_access_public(setup_env):
    from utilities.common_functions import user_has_group_access
    
    assert user_has_group_access(["group1"], [])


def test_user_has_group_access_match(setup_env):
    from utilities.common_functions import user_has_group_access
    
    assert user_has_group_access(["group1", "group2"], ["group2", "group3"])


def test_user_has_group_access_no_match(setup_env):
    from utilities.common_functions import user_has_group_access
    
    assert not user_has_group_access(["group1"], ["group2", "group3"])


def test_merge_fields_simple(setup_env):
    from utilities.common_functions import merge_fields
    
    source = {"field1": "value1", "field2": "value2"}
    target = {}
    result = merge_fields(source, target, ["field1"])
    assert result["field1"] == "value1"
    assert "field2" not in result


def test_merge_fields_nested(setup_env):
    from utilities.common_functions import merge_fields
    
    source = {"nested": {"field1": "value1"}}
    target = {}
    result = merge_fields(source, target, ["nested.field1"])
    assert result["nested"]["field1"] == "value1"


def test_get_property_path(setup_env):
    from utilities.common_functions import get_property_path
    
    data = {"level1": {"level2": {"value": "test"}}}
    assert get_property_path(data, "level1.level2.value") == "test"


def test_get_property_path_missing(setup_env):
    from utilities.common_functions import get_property_path
    
    data = {"level1": {}}
    assert get_property_path(data, "level1.missing") is None


def test_get_bearer_token(setup_env):
    from utilities.common_functions import get_bearer_token
    
    event = {"headers": {"Authorization": "Bearer token123"}}
    assert get_bearer_token(event) == "token123"


def test_get_bearer_token_lowercase(setup_env):
    from utilities.common_functions import get_bearer_token
    
    event = {"headers": {"authorization": "bearer token456"}}
    assert get_bearer_token(event) == "token456"


def test_get_bearer_token_missing(setup_env):
    from utilities.common_functions import get_bearer_token
    
    event = {"headers": {}}
    assert get_bearer_token(event) is None


def test_get_account_and_partition_from_env(setup_env, monkeypatch):
    from utilities.common_functions import get_account_and_partition
    
    monkeypatch.setenv("AWS_ACCOUNT_ID", "123456789012")
    monkeypatch.setenv("AWS_PARTITION", "aws")
    
    account, partition = get_account_and_partition()
    assert account == "123456789012"
    assert partition == "aws"


def test_get_account_and_partition_from_ecr(setup_env, monkeypatch):
    from utilities.common_functions import get_account_and_partition
    
    monkeypatch.delenv("AWS_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("ECR_REPOSITORY_ARN", "arn:aws:ecr:us-east-1:123456789012:repository/test")
    
    account, partition = get_account_and_partition()
    assert account == "123456789012"
    assert partition == "aws"


def test_generate_html_response(setup_env):
    from utilities.common_functions import generate_html_response
    
    response = generate_html_response(200, {"message": "success"})
    assert response["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in response["headers"]


def test_get_item_with_items():
    from utilities.common_functions import get_item
    
    response = {"Items": [{"id": "1"}]}
    result = get_item(response)
    if result:
        assert result["id"] == "1"


def test_get_item_empty(setup_env):
    from utilities.common_functions import get_item
    
    response = {"Items": []}
    assert get_item(response) is None
