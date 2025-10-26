# Lambda Testing Guide

## Common Mock Auth Fixture

All lambda tests now use a common `mock_auth` fixture defined in `conftest.py`. This provides consistent mocking of authentication functions across all tests.

### Usage

The `mock_auth` fixture is automatically available in all test functions via the `setup_auth_patches` autouse fixture.

#### Basic Usage

```python
def test_my_function(lambda_context, mock_auth):
    # Set the user context for this test
    mock_auth.set_user(username="test-user", groups=["test-group"], is_admin=False)
    
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}
    response = my_function(event, lambda_context)
    
    assert response["statusCode"] == 200
```

#### Admin User

```python
def test_admin_function(lambda_context, mock_auth):
    # Set admin user
    mock_auth.set_user(username="admin-user", groups=["admin"], is_admin=True)
    
    event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}
    response = admin_function(event, lambda_context)
    
    assert response["statusCode"] == 200
```

#### Multiple Users in Same Test

```python
def test_different_users(lambda_context, mock_auth):
    # Test with regular user
    mock_auth.set_user("user1", ["group1"], False)
    response1 = my_function(event1, lambda_context)
    assert response1["statusCode"] == 200
    
    # Test with admin user
    mock_auth.set_user("admin", ["admin"], True)
    response2 = my_function(event2, lambda_context)
    assert response2["statusCode"] == 200
```

### MockAuth API

The `MockAuth` class provides the following methods:

- `set_user(username, groups, is_admin)` - Set the current user context
- `reset()` - Reset to default test user ("test-user", ["test-group"], False)

The following mocked functions are automatically patched:
- `utilities.auth.get_username(event)` - Returns the configured username
- `utilities.auth.get_groups(event)` - Returns the configured groups list
- `utilities.auth.is_admin(event)` - Returns the configured is_admin boolean
- `utilities.auth.get_user_context(event)` - Returns tuple (username, is_admin)

### Common Fixtures

The following fixtures are available from `conftest.py`:

- `mock_auth` - MockAuth instance for controlling user context
- `lambda_context` - Standard Lambda context object
- `aws_credentials` - Sets up mock AWS credentials
- `setup_auth_patches` - Autouse fixture that patches auth functions

### Migration Guide

When updating existing tests:

1. Remove local mock setup code for auth functions
2. Add `mock_auth` parameter to test functions
3. Use `mock_auth.set_user()` instead of manually setting mock return values
4. Remove manual reset code - the fixture handles cleanup automatically

#### Before:
```python
def test_function(lambda_context):
    mock_common.get_username.return_value = "test-user"
    mock_common.is_admin.return_value = False
    
    # test code
    
    # Reset mocks
    mock_common.get_username.return_value = "default-user"
    mock_common.is_admin.return_value = False
```

#### After:
```python
def test_function(lambda_context, mock_auth):
    mock_auth.set_user("test-user", [], False)
    
    # test code
    # No manual cleanup needed!
```

### Additional Utilities

- `mock_api_wrapper` - Standard API wrapper for lambda responses
- `retry_config` - Standard boto3 retry configuration

These can be imported from conftest:
```python
from conftest import mock_api_wrapper, retry_config
```
