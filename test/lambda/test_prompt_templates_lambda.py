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

"""Test module for prompt templates lambda functions - refactored version using fixture-based mocking."""

import json
import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws


@pytest.fixture
def mock_prompt_templates_common():
    """Common mocks for prompt templates lambda functions."""

    def mock_api_wrapper(func):
        """Mock API wrapper that handles both success and error cases for testing."""

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

    # Set up environment variables
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "PROMPT_TEMPLATES_TABLE_NAME": "prompt-templates-table",
        "PROMPT_TEMPLATES_BY_LATEST_INDEX_NAME": "by-latest-index",
        "ADMIN_GROUP": "admin-group",
        "LISA_RAG_VECTOR_STORE_TABLE": "vector-store-table",
        "RAG_DOCUMENT_TABLE": "document-table",
        "RAG_SUB_DOCUMENT_TABLE": "sub-document-table",
        "PROMPT_TEMPLATES_TABLE": "prompt-templates-table",
    }

    retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

    with patch.dict(os.environ, env_vars), patch("utilities.auth.get_username") as mock_get_username, patch(
        "utilities.common_functions.get_groups"
    ) as mock_get_groups, patch("utilities.auth.is_admin") as mock_is_admin, patch(
        "utilities.common_functions.retry_config", retry_config
    ), patch(
        "utilities.common_functions.api_wrapper", mock_api_wrapper
    ), patch.dict(
        "sys.modules", {"create_env_variables": MagicMock()}
    ):

        # Set up default mock return values
        mock_get_username.return_value = "test-user"
        mock_get_groups.return_value = ["test-group"]
        mock_is_admin.return_value = False

        yield {
            "get_username": mock_get_username,
            "get_groups": mock_get_groups,
            "is_admin": mock_is_admin,
            "api_wrapper": mock_api_wrapper,
            "retry_config": retry_config,
        }


@pytest.fixture
def prompt_templates_functions(mock_prompt_templates_common):
    """Import prompt templates lambda functions with mocked dependencies."""
    from prompt_templates.lambda_functions import _get_prompt_templates, create, delete, get, list, update

    return {
        "_get_prompt_templates": _get_prompt_templates,
        "create": create,
        "delete": delete,
        "get": get,
        "list": list,
        "update": update,
    }


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
    """Sample prompt template for testing."""
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


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for prompt templates."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
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
        yield table


class TestCreatePromptTemplate:
    """Test class for creating prompt templates."""

    def test_create_prompt_template(self, prompt_templates_functions, dynamodb_table, lambda_context):
        """Test creating a new prompt template."""
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(
                {
                    "title": "Test Template",
                    "groups": ["test-group"],
                    "type": "persona",
                    "body": "Test prompt template body",
                }
            ),
        }

        response = prompt_templates_functions["create"](event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["title"] == "Test Template"
        assert body["owner"] == "test-user"
        assert body["groups"] == ["test-group"]
        assert body["type"] == "persona"
        assert body["body"] == "Test prompt template body"


class TestUpdatePromptTemplate:
    """Test class for updating prompt templates."""

    def test_update_prompt_template(self, prompt_templates_functions, dynamodb_table, lambda_context):
        """Test updating a prompt template."""
        # Create initial template
        create_response = prompt_templates_functions["create"](
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
        assert create_response["statusCode"] == 200
        data = json.loads(create_response["body"])
        template_id = data["id"]

        # Update template
        update_response = prompt_templates_functions["update"](
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

        assert update_response["statusCode"] == 200
        data = json.loads(update_response["body"])
        assert data["title"] == "Updated Template"
        assert data["body"] == "Updated prompt template body"

    def test_update_prompt_template_unauthorized(
        self,
        prompt_templates_functions,
        mock_prompt_templates_common,
        dynamodb_table,
        sample_prompt_template,
        lambda_context,
    ):
        """Test updating a prompt template without authorization."""
        # Add the template to the table first
        dynamodb_table.put_item(Item=sample_prompt_template)

        # Mock different user
        mock_prompt_templates_common["get_username"].return_value = "different-user"
        mock_prompt_templates_common["is_admin"].return_value = False

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

        response = prompt_templates_functions["update"](event, lambda_context)
        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "Not authorized to update test-template" in body.get("error", "")

    def test_update_template_url_id_mismatch(
        self, prompt_templates_functions, dynamodb_table, sample_prompt_template, lambda_context
    ):
        """Test update with mismatched IDs between URL and body."""
        # Add the template to the table first
        dynamodb_table.put_item(Item=sample_prompt_template)

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

        response = prompt_templates_functions["update"](event, lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "URL id test-template doesn't match body id different-id" in body.get("error", "")

    def test_update_template_not_found(self, prompt_templates_functions, dynamodb_table, lambda_context):
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

        response = prompt_templates_functions["update"](event, lambda_context)
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "not found" in body.get("error", "")

    def test_admin_can_update_any_template(
        self,
        prompt_templates_functions,
        mock_prompt_templates_common,
        dynamodb_table,
        sample_prompt_template,
        lambda_context,
    ):
        """Test that an admin can update any template."""
        # Add the template to the table first
        dynamodb_table.put_item(Item=sample_prompt_template)

        # Set up admin user
        mock_prompt_templates_common["get_username"].return_value = "admin-user"
        mock_prompt_templates_common["is_admin"].return_value = True

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
        response = prompt_templates_functions["update"](event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["title"] == "Admin Updated Template"
        assert body["body"] == "Admin updated body"


class TestGetPromptTemplate:
    """Test class for getting prompt templates."""

    def test_get_prompt_template(
        self, prompt_templates_functions, dynamodb_table, sample_prompt_template, lambda_context
    ):
        """Test getting a specific prompt template."""
        # Add the template to the table
        dynamodb_table.put_item(Item=sample_prompt_template)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"promptTemplateId": "test-template"},
        }

        response = prompt_templates_functions["get"](event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["id"] == "test-template"
        assert body["owner"] == "test-user"

    def test_get_prompt_template_not_found(self, prompt_templates_functions, dynamodb_table, lambda_context):
        """Test getting a non-existent prompt template."""
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"promptTemplateId": "non-existent"},
        }

        response = prompt_templates_functions["get"](event, lambda_context)
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "Prompt template non-existent not found" in body.get("error", "")

    def test_get_prompt_template_public(
        self,
        prompt_templates_functions,
        mock_prompt_templates_common,
        dynamodb_table,
        sample_prompt_template,
        lambda_context,
    ):
        """Test getting a public prompt template by different user."""
        # Add the template to the table
        dynamodb_table.put_item(Item=sample_prompt_template)

        # Mock different user
        mock_prompt_templates_common["get_username"].return_value = "different-user"
        mock_prompt_templates_common["is_admin"].return_value = False

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
            "pathParameters": {"promptTemplateId": "test-template"},
        }

        response = prompt_templates_functions["get"](event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["id"] == "test-template"
        assert body["owner"] == "test-user"

    def test_get_prompt_template_unauthorized(
        self,
        prompt_templates_functions,
        mock_prompt_templates_common,
        dynamodb_table,
        sample_prompt_template,
        lambda_context,
    ):
        """Test getting a prompt template without authorization."""
        # Add the template to the table with restricted groups
        sample_prompt = sample_prompt_template.copy()
        sample_prompt["groups"] = ["different-group"]
        dynamodb_table.put_item(Item=sample_prompt)

        # Mock different user with no access
        mock_prompt_templates_common["get_username"].return_value = "different-user"
        mock_prompt_templates_common["get_groups"].return_value = []
        mock_prompt_templates_common["is_admin"].return_value = False

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
            "pathParameters": {"promptTemplateId": "test-template"},
        }

        response = prompt_templates_functions["get"](event, lambda_context)
        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "Not authorized to get test-template" in body.get("error", "")


class TestDeletePromptTemplate:
    """Test class for deleting prompt templates."""

    def test_delete_prompt_template(
        self, prompt_templates_functions, dynamodb_table, sample_prompt_template, lambda_context
    ):
        """Test deleting a prompt template."""
        # Add the template to the table
        dynamodb_table.put_item(Item=sample_prompt_template)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"promptTemplateId": "test-template"},
        }

        response = prompt_templates_functions["delete"](event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "ok"

    def test_delete_prompt_template_not_found(self, prompt_templates_functions, dynamodb_table, lambda_context):
        """Test deleting a non-existent prompt template."""
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"promptTemplateId": "non-existent"},
        }

        response = prompt_templates_functions["delete"](event, lambda_context)
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "Prompt template non-existent not found" in body.get("error", "")

    def test_delete_prompt_template_unauthorized(
        self,
        prompt_templates_functions,
        mock_prompt_templates_common,
        dynamodb_table,
        sample_prompt_template,
        lambda_context,
    ):
        """Test deleting a prompt template without authorization."""
        # Add the template to the table first
        dynamodb_table.put_item(Item=sample_prompt_template)

        # Mock different user
        mock_prompt_templates_common["is_admin"].return_value = False
        mock_prompt_templates_common["get_username"].return_value = "different-user"

        event = {
            "pathParameters": {"promptTemplateId": "test-template"},
            "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
        }

        response = prompt_templates_functions["delete"](event, lambda_context)
        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "Not authorized to delete test-template" in body.get("error", "")

    def test_admin_can_delete_any_template(
        self,
        prompt_templates_functions,
        mock_prompt_templates_common,
        dynamodb_table,
        sample_prompt_template,
        lambda_context,
    ):
        """Test that an admin can delete any template."""
        # Add the template to the table first
        dynamodb_table.put_item(Item=sample_prompt_template)

        # Set up admin user
        mock_prompt_templates_common["get_username"].return_value = "admin-user"
        mock_prompt_templates_common["is_admin"].return_value = True

        event = {
            "pathParameters": {"promptTemplateId": "test-template"},
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        }

        # Admin should be able to delete the template despite not being the owner
        response = prompt_templates_functions["delete"](event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "ok"


class TestListPromptTemplates:
    """Test class for listing prompt templates."""

    def test_list_prompt_templates(
        self, prompt_templates_functions, mock_prompt_templates_common, dynamodb_table, lambda_context
    ):
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
        response = prompt_templates_functions["create"](create_event, lambda_context)
        assert response["statusCode"] == 200

        # List public templates as different user
        mock_prompt_templates_common["get_username"].return_value = "different-user"
        mock_prompt_templates_common["get_groups"].return_value = ["different-group"]

        list_event = {
            "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
            "queryStringParameters": {"public": "true"},
        }

        response = prompt_templates_functions["list"](list_event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["Items"]) == 1
        assert body["Items"][0]["title"] == "Public Template"
        assert "lisa:public" in body["Items"][0]["groups"]

    def test_list_prompt_templates_admin(
        self, prompt_templates_functions, mock_prompt_templates_common, dynamodb_table, lambda_context
    ):
        """Test listing prompt templates as admin."""
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
        response = prompt_templates_functions["create"](create_event, lambda_context)
        assert response["statusCode"] == 200

        # List templates as admin
        mock_prompt_templates_common["get_username"].return_value = "different-user"
        mock_prompt_templates_common["get_groups"].return_value = ["different-group"]
        mock_prompt_templates_common["is_admin"].return_value = True

        list_event = {
            "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
            "queryStringParameters": {"public": "true"},
        }

        response = prompt_templates_functions["list"](list_event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["Items"]) == 1
        assert body["Items"][0]["title"] == "Public Template"
        assert "lisa:public" in body["Items"][0]["groups"]

    def test_list_prompt_templates_for_user(self, prompt_templates_functions, dynamodb_table, lambda_context):
        """Test listing prompt templates for current user."""
        # Create a template
        create_event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(
                {
                    "title": "User Template",
                    "groups": ["lisa:public"],
                    "type": "persona",
                    "body": "User prompt template body",
                }
            ),
        }
        response = prompt_templates_functions["create"](create_event, lambda_context)
        assert response["statusCode"] == 200

        # List templates for user
        list_event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        }

        response = prompt_templates_functions["list"](list_event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["Items"]) == 1
        assert body["Items"][0]["title"] == "User Template"
        assert "lisa:public" in body["Items"][0]["groups"]


class TestPromptTemplatesHelper:
    """Test class for prompt templates helper functions."""

    def test_get_prompt_templates_helper(self, prompt_templates_functions, dynamodb_table, sample_prompt_template):
        """Test the _get_prompt_templates helper function with different parameters."""
        # Add a template to the table
        dynamodb_table.put_item(Item=sample_prompt_template)

        # Test getting templates for a specific user
        result = prompt_templates_functions["_get_prompt_templates"](user_id="test-user", latest=True)
        assert len(result["Items"]) == 1
        assert result["Items"][0]["id"] == "test-template"

        # Test getting templates for a specific group
        result = prompt_templates_functions["_get_prompt_templates"](groups=["lisa:public"], latest=True)
        assert len(result["Items"]) == 1
        assert result["Items"][0]["id"] == "test-template"

        # Test getting templates with no filters
        result = prompt_templates_functions["_get_prompt_templates"]()
        assert len(result["Items"]) == 1
        assert result["Items"][0]["id"] == "test-template"
