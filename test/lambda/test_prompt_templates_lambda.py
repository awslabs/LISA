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

import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["PROMPT_TEMPLATES_TABLE_NAME"] = "prompt-templates-table"
os.environ["PROMPT_TEMPLATES_BY_LATEST_INDEX_NAME"] = "by-latest-index"
os.environ["ADMIN_GROUP"] = "admin-group"
os.environ["LISA_RAG_VECTOR_STORE_TABLE"] = "vector-store-table"
os.environ["RAG_DOCUMENT_TABLE"] = "document-table"
os.environ["RAG_SUB_DOCUMENT_TABLE"] = "sub-document-table"
os.environ["PROMPT_TEMPLATES_TABLE"] = "prompt-templates-table"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


# Define a mock API wrapper for testing
def mock_api_wrapper(func):
    """Mock API wrapper that handles both success and error cases for testing.

    For successful function calls, it wraps the result in an HTTP response format.
    For error cases, it returns an appropriate error response with proper status code.
    """

    def wrapper(event, context):
        try:
            # Call the function and wrap successful results in an HTTP response
            result = func(event, context)
            return {
                "statusCode": 200,
                "body": json.dumps(result, default=str),
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
            }
        except ValueError as e:
            error_msg = str(e)
            # For tests that need to assert specific errors with pytest.raises, re-raise
            if "test" in event.get("raise_errors", ""):
                raise

            # Handle specific error patterns with appropriate status codes
            status_code = 400
            if "not found" in error_msg.lower():
                status_code = 404
            elif "Not authorized" in error_msg:
                status_code = 403

            return {
                "statusCode": status_code,
                "body": json.dumps({"error": error_msg}, default=str),
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
            }
        except Exception as e:
            # For other errors, return a general 400 response
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Bad Request: {str(e)}"}, default=str),
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
            }

    return wrapper


# Create mock modules
mock_common = MagicMock()
mock_common.get_username.return_value = "test-user"
mock_common.get_groups.return_value = ["test-group"]
mock_common.is_admin.return_value = False
mock_common.get_user_context.return_value = ("test-user", False, ["test-group"])
mock_common.retry_config = retry_config
mock_common.api_wrapper = mock_api_wrapper  # Add the mock API wrapper

# Create mock create_env_variables
mock_create_env = MagicMock()

# First, patch sys.modules
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
    },
).start()

# Then patch the specific functions
patch("utilities.auth.get_username", mock_common.get_username).start()
patch("utilities.auth.get_groups", mock_common.get_groups).start()
patch("utilities.auth.is_admin", mock_common.is_admin).start()
patch("utilities.auth.get_user_context", mock_common.get_user_context).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()  # Patch the API wrapper

# Now import the lambda functions
from prompt_templates.lambda_functions import _get_prompt_templates, create, delete, get, list, update


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def sample_prompt_template():
    return {
        "id": "test-template",
        "created": datetime.now().isoformat(),
        "owner": "test-user",
        "groups": ["lisa:public"],
        "title": "Test Template",
        "revision": 1,
        "latest": True,
        "type": "persona",
        "body": "Test prompt template body",
    }


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def prompt_templates_table(dynamodb):
    """Create a mock DynamoDB table for prompt templates."""
    table = dynamodb.create_table(
        TableName="prompt-templates-table",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}, {"AttributeName": "created", "KeyType": "RANGE"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "created", "AttributeType": "S"},
            {"AttributeName": "latest", "AttributeType": "BOOL"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by-latest-index",
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"},
                    {"AttributeName": "latest", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture(scope="function")
def mock_boto3_client():
    """Mock boto3 client for AWS services."""
    with mock_aws():
        yield boto3.client


@pytest.fixture
def mock_is_admin():
    """Mocks the is_admin function."""
    # Save the original mock value
    original_return_value = mock_common.is_admin.return_value

    # Update to return True (or other value as needed for specific tests)
    mock_common.is_admin.return_value = False

    yield mock_common.is_admin

    # Restore the original mock value after the test
    mock_common.is_admin.return_value = original_return_value


def test_create_prompt_template(prompt_templates_table, lambda_context):
    """Test creating a new prompt template."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {"title": "Test Template", "groups": ["test-group"], "type": "persona", "body": "Test prompt template body"}
        ),
    }

    response = create(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["title"] == "Test Template"
    assert body["owner"] == "test-user"
    assert body["groups"] == ["test-group"]
    assert body["type"] == "persona"
    assert body["body"] == "Test prompt template body"


def test_update_prompt_template(prompt_templates_table, lambda_context):
    """Test updating a prompt template."""
    # Create initial template
    response = create(
        {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(
                {
                    "title": "Test Template",
                    "groups": ["test-group"],
                    "type": "persona",
                    "body": "Test prompt template body",
                }
            ),
        },
        lambda_context,
    )
    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    template_id = data["id"]

    # Update template
    response = update(
        {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"promptTemplateId": template_id},
            "body": json.dumps(
                {
                    "id": template_id,
                    "title": "Updated Template",
                    "groups": ["test-group"],
                    "type": "persona",
                    "body": "Updated prompt template body",
                    "owner": "test-user",
                }
            ),
        },
        lambda_context,
    )

    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    assert data["title"] == "Updated Template"
    assert data["body"] == "Updated prompt template body"


@pytest.mark.asyncio
async def test_get_prompt_template_not_found(mock_boto3_client, prompt_templates_table, lambda_context):
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"promptTemplateId": "non-existent"},
    }

    response = get(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "Prompt template non-existent not found" in body.get("error", "")


@pytest.mark.asyncio
async def test_delete_prompt_template_not_found(mock_boto3_client, prompt_templates_table, lambda_context):
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"promptTemplateId": "non-existent"},
    }

    response = delete(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "Prompt template non-existent not found" in body.get("error", "")


def test_list_prompt_templates(prompt_templates_table, lambda_context, mock_is_admin):
    """Test listing prompt templates."""
    # Create a public template
    create_event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {
                "title": "Public Template",
                "groups": ["lisa:public"],
                "type": "persona",
                "body": "Public prompt template body",
            }
        ),
    }
    response = create(create_event, lambda_context)
    assert response["statusCode"] == 200

    # List public templates
    list_event = {
        "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
        "queryStringParameters": {"public": "true"},
    }
    mock_common.get_username.return_value = "different-user"
    mock_common.get_groups.return_value = ["different-group"]

    response = list(list_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["Items"]) == 1
    assert body["Items"][0]["title"] == "Public Template"
    assert "lisa:public" in body["Items"][0]["groups"]

    # Reset mock
    mock_common.get_username.return_value = "test-user"
    mock_common.get_groups.return_value = ["test-group"]


def test_list_prompt_templates_admin(prompt_templates_table, lambda_context, mock_is_admin):
    """Test listing prompt templates."""
    # Create a public template
    create_event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {
                "title": "Public Template",
                "groups": ["lisa:public"],
                "type": "persona",
                "body": "Public prompt template body",
            }
        ),
    }
    response = create(create_event, lambda_context)
    assert response["statusCode"] == 200

    # List public templates
    list_event = {
        "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
        "queryStringParameters": {"public": "true"},
    }
    mock_common.get_username.return_value = "different-user"
    mock_common.get_groups.return_value = ["different-group"]

    # Set admin to True for this test to increase coverage
    mock_is_admin.return_value = True

    response = list(list_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["Items"]) == 1
    assert body["Items"][0]["title"] == "Public Template"
    assert "lisa:public" in body["Items"][0]["groups"]

    # Reset mock
    mock_common.get_username.return_value = "test-user"
    mock_common.get_groups.return_value = ["test-group"]
    mock_is_admin.return_value = False


def test_list_prompt_templates_for_user(prompt_templates_table, lambda_context):
    """Test listing prompt templates."""
    # Create a public template
    create_event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {
                "title": "Public Template",
                "groups": ["lisa:public"],
                "type": "persona",
                "body": "Public prompt template body",
            }
        ),
    }
    response = create(create_event, lambda_context)
    assert response["statusCode"] == 200

    # List public templates
    list_event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
    }

    response = list(list_event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["Items"]) == 1
    assert body["Items"][0]["title"] == "Public Template"
    assert "lisa:public" in body["Items"][0]["groups"]


def test_delete_prompt_template(prompt_templates_table, sample_prompt_template, lambda_context):
    """Test deleting a prompt template."""
    # Add the template to the table
    prompt_templates_table.put_item(Item=sample_prompt_template)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"promptTemplateId": "test-template"},
    }

    response = delete(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ok"


def test_get_prompt_template(prompt_templates_table, sample_prompt_template, lambda_context):
    """Test getting a specific prompt template."""
    # Add the template to the table
    prompt_templates_table.put_item(Item=sample_prompt_template)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"promptTemplateId": "test-template"},
    }

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "test-template"
    assert body["owner"] == "test-user"


def test_get_prompt_template_public(prompt_templates_table, sample_prompt_template, lambda_context, mock_is_admin):
    """Test getting a specific prompt template."""
    # Add the template to the table
    prompt_templates_table.put_item(Item=sample_prompt_template)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"promptTemplateId": "test-template"},
    }

    mock_common.get_username.return_value = "different-user"
    mock_is_admin.return_value = False

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "test-template"
    assert body["owner"] == "test-user"

    # Reset mocks
    mock_common.get_username.return_value = "test-user"


def test_update_prompt_template_unauthorized(
    prompt_templates_table, sample_prompt_template, lambda_context, mock_is_admin
):
    """Test updating a prompt template without authorization."""
    # Add the template to the table first
    prompt_templates_table.put_item(Item=sample_prompt_template)

    mock_common.get_username.return_value = "different-user"
    mock_common.get_user_context.return_value = ("different-user", False, ["test-group"])
    mock_is_admin.return_value = False
    event = {
        "pathParameters": {"promptTemplateId": "test-template"},
        "body": json.dumps(
            {
                "id": "test-template",
                "title": "Updated Template",
                "owner": "test-user",
                "groups": ["test-group"],
                "type": "persona",
                "body": "Updated body",
            }
        ),
        "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to update test-template" in body.get("error", "")

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_common.get_user_context.return_value = ("test-user", False, ["test-group"])


def test_delete_prompt_template_unauthorized(
    prompt_templates_table, sample_prompt_template, lambda_context, mock_is_admin
):
    """Test deleting a prompt template without authorization."""
    # Add the template to the table first
    prompt_templates_table.put_item(Item=sample_prompt_template)

    mock_is_admin.return_value = False
    mock_common.get_username.return_value = "different-user"
    mock_common.get_user_context.return_value = ("different-user", False, ["test-group"])
    event = {
        "pathParameters": {"promptTemplateId": "test-template"},
        "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
    }

    response = delete(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to delete test-template" in body.get("error", "")

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_common.get_user_context.return_value = ("test-user", False, ["test-group"])


def test_get_prompt_template_unauthorized(
    prompt_templates_table, sample_prompt_template, lambda_context, mock_is_admin
):
    """Test getting a specific prompt template."""
    # Add the template to the table
    sample_prompt = sample_prompt_template
    sample_prompt["groups"] = ["different-group"]
    prompt_templates_table.put_item(Item=sample_prompt)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
        "pathParameters": {"promptTemplateId": "test-template"},
    }

    mock_common.get_username.return_value = "different-user"
    mock_common.get_groups.return_value = []
    mock_common.get_user_context.return_value = ("different-user", False, [])
    mock_is_admin.return_value = False

    response = get(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to get test-template" in body.get("error", "")

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_common.get_groups.return_value = ["test-group"]
    mock_common.get_user_context.return_value = ("test-user", False, ["test-group"])


# Add a new test to test the admin path with increased coverage
def test_admin_can_update_any_template(prompt_templates_table, sample_prompt_template, lambda_context, mock_is_admin):
    """Test that an admin can update any template."""
    # Add the template to the table first
    prompt_templates_table.put_item(Item=sample_prompt_template)

    # Set up admin user
    mock_common.get_username.return_value = "admin-user"
    mock_is_admin.return_value = True

    event = {
        "pathParameters": {"promptTemplateId": "test-template"},
        "body": json.dumps(
            {
                "id": "test-template",
                "title": "Admin Updated Template",
                "groups": ["test-group"],
                "type": "persona",
                "body": "Admin updated body",
                "owner": "test-user",
            }
        ),
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
    }

    # Admin should be able to update the template despite not being the owner
    response = update(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["title"] == "Admin Updated Template"
    assert body["body"] == "Admin updated body"

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_is_admin.return_value = False


def test_admin_can_delete_any_template(prompt_templates_table, sample_prompt_template, lambda_context, mock_is_admin):
    """Test that an admin can delete any template."""
    # Add the template to the table first
    prompt_templates_table.put_item(Item=sample_prompt_template)

    # Set up admin user
    mock_common.get_username.return_value = "admin-user"
    mock_is_admin.return_value = True

    event = {
        "pathParameters": {"promptTemplateId": "test-template"},
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
    }

    # Admin should be able to delete the template despite not being the owner
    response = delete(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ok"

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_is_admin.return_value = False


def test_update_template_url_id_mismatch(prompt_templates_table, sample_prompt_template, lambda_context):
    """Test update with mismatched IDs between URL and body."""
    # Add the template to the table first
    prompt_templates_table.put_item(Item=sample_prompt_template)

    event = {
        "pathParameters": {"promptTemplateId": "test-template"},
        "body": json.dumps(
            {
                "id": "different-id",
                "title": "Updated Template",
                "owner": "test-user",
                "groups": ["test-group"],
                "type": "persona",
                "body": "Updated body",
            }
        ),
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "URL id test-template doesn't match body id different-id" in body.get("error", "")


def test_update_template_not_found(prompt_templates_table, lambda_context):
    """Test updating a non-existent template."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"promptTemplateId": "non-existent"},
        "body": json.dumps(
            {
                "id": "non-existent",
                "title": "Updated Template",
                "owner": "test-user",
                "groups": ["test-group"],
                "type": "persona",
                "body": "Updated body",
            }
        ),
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in body.get("error", "")


def test_get_prompt_templates_helper(prompt_templates_table, sample_prompt_template):
    """Test the _get_prompt_templates helper function with different parameters."""
    # Add a template to the table
    prompt_templates_table.put_item(Item=sample_prompt_template)

    # Test getting templates for a specific user
    result = _get_prompt_templates(user_id="test-user", latest=True)
    assert len(result["Items"]) == 1
    assert result["Items"][0]["id"] == "test-template"

    # Test getting templates for a specific group
    result = _get_prompt_templates(groups=["lisa:public"], latest=True)
    assert len(result["Items"]) == 1
    assert result["Items"][0]["id"] == "test-template"

    # Test getting templates with no filters
    result = _get_prompt_templates()
    assert len(result["Items"]) == 1
    assert result["Items"][0]["id"] == "test-template"
