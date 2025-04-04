import json
import pytest
from moto import mock_aws
import boto3
import os
from datetime import datetime
from types import SimpleNamespace
import sys
from unittest.mock import MagicMock, patch
from botocore.config import Config
import functools
from decimal import Decimal

# Create a real retry config
retry_config = Config(
    retries=dict(
        max_attempts=3
    ),
    defaults_mode='standard'
)

def api_wrapper(func):
    """Real API wrapper for testing."""
    @functools.wraps(func)
    def wrapper(event, context):
        try:
            result = func(event, context)
            if isinstance(result, dict) and "statusCode" in result:
                return result
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(result)
            }
        except ValueError as e:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({"error": str(e)})
            }
        except Exception as e:
            print(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({"error": str(e)})
            }
    return wrapper

# Set up environment variables first
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["SESSIONS_TABLE_NAME"] = "sessions-table"
os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"] = "sessions-by-user-id-index"

# Create mock modules
mock_common = MagicMock()
mock_common.get_username = MagicMock(return_value="test-user")
mock_common.retry_config = retry_config
mock_common.api_wrapper = api_wrapper

# Create a mock create_env_variables module
mock_create_env = MagicMock()
sys.modules['create_env_variables'] = mock_create_env

# Patch the common functions
patch('utilities.common_functions.get_username', mock_common.get_username).start()
patch('utilities.common_functions.retry_config', retry_config).start()
patch('utilities.common_functions.api_wrapper', api_wrapper).start()

# Now import the lambda functions
from session.lambda_functions import (
    list_sessions,
    get_session,
    delete_session,
    delete_user_sessions,
    put_session
)

@pytest.fixture(autouse=True)
def setup_aws_credentials():
    """Setup AWS credentials for each test."""
    with mock_aws():
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        yield

@pytest.fixture
def dynamodb_table(setup_aws_credentials):
    """Create a DynamoDB table for testing."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="sessions-table",
            KeySchema=[
                {"AttributeName": "sessionId", "KeyType": "HASH"},
                {"AttributeName": "userId", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "sessionId", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "sessions-by-user-id-index",
                    "KeySchema": [
                        {"AttributeName": "userId", "KeyType": "HASH"},
                        {"AttributeName": "sessionId", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 1,
                        "WriteCapacityUnits": 1
                    }
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        yield table

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
        log_stream_name="2024/03/27/[$LATEST]test123"
    )

@pytest.fixture
def sample_session():
    return {
        "sessionId": "test-session",
        "userId": "test-user",
        "history": [
            {"type": "human", "content": "Hello"},
            {"type": "assistant", "content": "Hi there!"}
        ],
        "configuration": {"model": "test-model"},
        "startTime": datetime.now().isoformat(),
        "createTime": datetime.now().isoformat()
    }

def test_list_sessions(dynamodb_table, sample_session, lambda_context):
    # Create a few sessions
    dynamodb_table.put_item(Item=sample_session)
    
    session2 = sample_session.copy()
    session2["sessionId"] = "test-session-2"
    dynamodb_table.put_item(Item=session2)
    
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        }
    }
    
    response = list_sessions(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 2
    assert any(s["sessionId"] == "test-session" for s in body)
    assert any(s["sessionId"] == "test-session-2" for s in body)

def test_get_session(dynamodb_table, sample_session, lambda_context):
    dynamodb_table.put_item(Item=sample_session)
    
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        },
        "pathParameters": {
            "sessionId": "test-session"
        }
    }
    
    response = get_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["sessionId"] == sample_session["sessionId"]
    assert body["userId"] == "test-user"

def test_delete_session(dynamodb_table, sample_session, lambda_context):
    dynamodb_table.put_item(Item=sample_session)
    
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        },
        "pathParameters": {
            "sessionId": "test-session"
        }
    }
    
    response = delete_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["deleted"] is True

def test_delete_user_sessions(dynamodb_table, sample_session, lambda_context):
    # Create multiple sessions
    dynamodb_table.put_item(Item=sample_session)
    
    session2 = sample_session.copy()
    session2["sessionId"] = "test-session-2"
    dynamodb_table.put_item(Item=session2)
    
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        }
    }
    
    response = delete_user_sessions(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["deleted"] is True

def test_put_session(dynamodb_table, sample_session, lambda_context):
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        },
        "pathParameters": {
            "sessionId": "test-session"
        },
        "body": json.dumps({
            "messages": sample_session["history"],
            "configuration": sample_session["configuration"]
        }, default=str)
    }
    
    response = put_session(event, lambda_context)
    assert response["statusCode"] == 200

def test_get_session_not_found(dynamodb_table, lambda_context):
    """Test getting a non-existent session."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        },
        "pathParameters": {
            "sessionId": "non-existent-session"
        }
    }
    
    response = get_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body == {}

def test_delete_session_not_found(dynamodb_table, lambda_context):
    """Test deleting a non-existent session."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        },
        "pathParameters": {
            "sessionId": "non-existent-session"
        }
    }
    
    response = delete_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["deleted"] is True

def test_put_session_invalid_body(dynamodb_table, lambda_context):
    """Test putting a session with invalid body."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        },
        "pathParameters": {
            "sessionId": "test-session"
        },
        "body": "invalid-json"
    }
    
    response = put_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Invalid JSON" in body["error"]

def test_put_session_missing_required_fields(dynamodb_table, lambda_context):
    """Test putting a session with missing required fields."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        },
        "pathParameters": {
            "sessionId": "test-session"
        },
        "body": json.dumps({})
    }
    
    response = put_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Missing required fields" in body["error"]

def test_list_sessions_empty(dynamodb_table, lambda_context):
    """Test listing sessions when there are none."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        }
    }
    
    response = list_sessions(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 0

def test_missing_path_parameters(lambda_context):
    """Test handling missing path parameters."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "username": "test-user"
                }
            }
        }
    }
    
    response = get_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Missing sessionId" in body["error"]

def test_missing_username(lambda_context):
    """Test handling missing username in claims."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {}
            }
        },
        "pathParameters": {
            "sessionId": "test-session"
        }
    }
    
    response = get_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Missing username" in body["error"]