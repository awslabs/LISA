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

"""Unit tests for CreateModel audit logging."""
import json
import logging
import os
from unittest.mock import MagicMock, patch

# Set mock AWS credentials BEFORE any imports that use them
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["MODEL_TABLE_NAME"] = "model-table"
os.environ["LISA_RAG_VECTOR_STORE_TABLE"] = "vector-store-table"
os.environ["GUARDRAILS_TABLE_NAME"] = "guardrails-table"
os.environ["LISA_RAG_VECTOR_STORE_TABLE_PS_NAME"] = "/test/ragVectorStoreTableName"
os.environ["LISA_RAG_COLLECTIONS_TABLE_PS_NAME"] = "/test/ragCollectionsTableName"
os.environ["CREATE_SFN_ARN"] = "arn:aws:states:us-east-1:123456789012:stateMachine:CreateModelStateMachine"
os.environ["DELETE_SFN_ARN"] = "arn:aws:states:us-east-1:123456789012:stateMachine:DeleteModelStateMachine"
os.environ["UPDATE_SFN_ARN"] = "arn:aws:states:us-east-1:123456789012:stateMachine:UpdateModelStateMachine"
os.environ["ADMIN_GROUP"] = "admin-group"

import pytest
from fastapi import Request
from models.domain_objects import (
    AutoScalingConfig,
    ContainerConfig,
    ContainerConfigImage,
    ContainerHealthCheckConfig,
    CreateModelRequest,
    MetricConfig,
    ModelType,
)
from models.lambda_functions import create_model


class TestCreateModelAuditLogging:
    """Test audit logging for CreateModel API endpoint."""

    @pytest.mark.asyncio
    async def test_create_model_logs_all_required_fields(self, caplog):
        """Test that CreateModel logs contain all required security audit fields."""
        # Setup mock request with API Gateway event context
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "username": "test-admin",
                        "groups": json.dumps(["admin-group"]),
                        "authType": "JWT",
                    },
                    "identity": {
                        "sourceIp": "192.168.1.100",
                    },
                },
            }
        }

        # Create request with container config (non-LISA hosted model)
        create_request = CreateModelRequest(
            modelId="test-model-123",
            modelName="test-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=True,
            modelUrl="https://example.com/model-endpoint",
        )

        # Mock the handler and auth functions
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks
            mock_is_admin.return_value = True
            mock_get_groups.return_value = ["admin-group"]
            mock_get_username.return_value = "test-admin"

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.return_value = MagicMock()

            # Call the endpoint
            await create_model(create_request, mock_request)

            # Verify log was created
            assert len(caplog.records) > 0

            # Find the CreateModel request log entry
            log_record = None
            for record in caplog.records:
                if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_REQUEST":
                    log_record = record
                    break

            assert log_record is not None, "CREATE_MODEL_REQUEST log entry not found"

            # Verify user context fields
            assert hasattr(log_record, "user")
            assert log_record.user["username"] == "test-admin"
            assert log_record.user["auth_type"] == "JWT"
            assert log_record.user["source_ip"] == "192.168.1.100"

            # Verify model configuration fields
            assert hasattr(log_record, "model")
            assert log_record.model["model_id"] == "test-model-123"
            assert log_record.model["model_name"] == "test-model-name"

            # Verify container field is None for non-LISA hosted model
            assert log_record.container is None

    @pytest.mark.asyncio
    async def test_create_model_logs_container_details_for_lisa_hosted(self, caplog):
        """Test that CreateModel logs container details for LISA-hosted models."""
        from models.domain_objects import InferenceContainer, LoadBalancerConfig, LoadBalancerHealthCheckConfig

        # Setup mock request
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "username": "test-admin",
                        "groups": json.dumps(["admin-group"]),
                        "authType": "JWT",
                    },
                    "identity": {
                        "sourceIp": "192.168.1.100",
                    },
                },
            }
        }

        # Create LISA-hosted model request with all required fields
        create_request = CreateModelRequest(
            modelId="lisa-hosted-model",
            modelName="lisa-hosted-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=True,
            instanceType="t2.micro",
            autoScalingConfig=AutoScalingConfig(
                minCapacity=1,
                maxCapacity=3,
                desiredCapacity=2,
                metricConfig=MetricConfig(
                    estimatedInstanceWarmup=60,
                    targetValue=60,
                    albMetricName="RequestCountPerTarget",
                    duration=60,
                ),
                cooldown=60,
                defaultInstanceWarmup=60,
            ),
            containerConfig=ContainerConfig(
                image=ContainerConfigImage(
                    baseImage="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-model:latest",
                    type="ecr",
                ),
                sharedMemorySize=1024,
                healthCheckConfig=ContainerHealthCheckConfig(
                    command=["CMD-SHELL", "curl -f http://localhost:8080/health"],
                    interval=30,
                    startPeriod=60,
                    timeout=10,
                    retries=3,
                ),
            ),
            loadBalancerConfig=LoadBalancerConfig(
                healthCheckConfig=LoadBalancerHealthCheckConfig(
                    healthyThresholdCount=2,
                    unhealthyThresholdCount=2,
                    path="/health",
                    port="8080",
                    protocol="HTTP",
                    timeout=5,
                    interval=10,
                )
            ),
            inferenceContainer=InferenceContainer.VLLM,
        )

        # Mock the handler and auth functions
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks
            mock_is_admin.return_value = True
            mock_get_groups.return_value = ["admin-group"]
            mock_get_username.return_value = "test-admin"

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.return_value = MagicMock()

            # Call the endpoint
            await create_model(create_request, mock_request)

            # Find the CreateModel request log entry
            log_record = None
            for record in caplog.records:
                if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_REQUEST":
                    log_record = record
                    break

            assert log_record is not None

            # Verify container image details are logged
            assert hasattr(log_record, "container")
            assert log_record.container["base_image"] == "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-model:latest"
            assert log_record.container["registry_domain"] == "123456789012.dkr.ecr.us-east-1.amazonaws.com"
            assert log_record.container["image_type"] == "ecr"
            assert log_record.container["healthcheck_command"] == ["CMD-SHELL", "curl -f http://localhost:8080/health"]

            # Verify model config includes instance type and autoscaling
            assert log_record.model["instance_type"] == "t2.micro"
            assert log_record.model["auto_scaling"]["min_capacity"] == 1
            assert log_record.model["auto_scaling"]["max_capacity"] == 3

    @pytest.mark.asyncio
    async def test_create_model_logs_without_container_config(self, caplog):
        """Test that CreateModel logs work when containerConfig is not provided."""
        # Setup mock request
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "username": "test-admin",
                        "groups": json.dumps(["admin-group"]),
                        "authType": "API_KEY",
                    },
                    "identity": {
                        "sourceIp": "10.0.0.50",
                    },
                },
            }
        }

        # Create request WITHOUT container config
        create_request = CreateModelRequest(
            modelId="simple-model",
            modelName="simple-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=False,
        )

        # Mock the handler and auth functions
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks
            mock_is_admin.return_value = True
            mock_get_groups.return_value = ["admin-group"]
            mock_get_username.return_value = "test-admin"

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.return_value = MagicMock()

            # Call the endpoint
            await create_model(create_request, mock_request)

            # Find the CreateModel request log entry
            log_record = None
            for record in caplog.records:
                if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_REQUEST":
                    log_record = record
                    break

            assert log_record is not None

            # Verify container field is None when no containerConfig
            assert log_record.container is None

            # Verify other fields still present
            assert log_record.user["username"] == "test-admin"
            assert log_record.model["model_id"] == "simple-model"

    @pytest.mark.asyncio
    async def test_create_model_does_not_log_sensitive_data(self, caplog):
        """Test that sensitive data like secrets and tokens are not logged."""
        # Setup mock request
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "username": "test-admin",
                        "groups": json.dumps(["admin-group"]),
                        "authType": "JWT",
                        "token": "super-secret-jwt-token-12345",  # Should NOT be logged
                    },
                    "identity": {
                        "sourceIp": "192.168.1.100",
                        "accessKey": "AKIAIOSFODNN7EXAMPLE",  # Should NOT be logged
                    },
                },
            }
        }

        # Create request
        create_request = CreateModelRequest(
            modelId="test-model",
            modelName="test-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=True,
        )

        # Mock the handler and auth functions
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks
            mock_is_admin.return_value = True
            mock_get_groups.return_value = ["admin-group"]
            mock_get_username.return_value = "test-admin"

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.return_value = MagicMock()

            # Call the endpoint
            await create_model(create_request, mock_request)

            # Find the CreateModel request log entry
            log_record = None
            for record in caplog.records:
                if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_REQUEST":
                    log_record = record
                    break

            assert log_record is not None

            # Verify sensitive data is NOT in the logged user context
            assert "token" not in log_record.user
            assert "accessKey" not in log_record.user

            # Get all log record attributes as strings to check they're not accidentally logged
            record_str = str(vars(log_record))
            assert "super-secret-jwt-token-12345" not in record_str
            assert "AKIAIOSFODNN7EXAMPLE" not in record_str

            # Verify non-sensitive data IS in logs
            assert log_record.user["username"] == "test-admin"
            assert log_record.model["model_id"] == "test-model"

    @pytest.mark.asyncio
    async def test_create_model_logs_for_successful_request(self, caplog):
        """Test that logs are written for successful CreateModel requests."""
        # Setup mock request
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "username": "test-admin",
                        "groups": json.dumps(["admin-group"]),
                        "authType": "JWT",
                    },
                    "identity": {
                        "sourceIp": "192.168.1.100",
                    },
                },
            }
        }

        create_request = CreateModelRequest(
            modelId="success-model",
            modelName="success-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=True,
        )

        # Mock the handler and auth functions
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks for successful creation
            mock_is_admin.return_value = True
            mock_get_groups.return_value = ["admin-group"]
            mock_get_username.return_value = "test-admin"

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.return_value = MagicMock()

            # Call the endpoint
            await create_model(create_request, mock_request)

            # Verify both request and success logs exist
            event_types = [getattr(record, "event_type", None) for record in caplog.records]
            assert "CREATE_MODEL_REQUEST" in event_types
            assert "CREATE_MODEL_SUCCESS" in event_types

    @pytest.mark.asyncio
    async def test_create_model_logs_for_failed_request(self, caplog):
        """Test that logs are written for failed CreateModel requests."""
        from models.exception import ModelAlreadyExistsError

        # Setup mock request
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "username": "test-admin",
                        "groups": json.dumps(["admin-group"]),
                        "authType": "JWT",
                    },
                    "identity": {
                        "sourceIp": "192.168.1.100",
                    },
                },
            }
        }

        create_request = CreateModelRequest(
            modelId="existing-model",
            modelName="existing-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=True,
        )

        # Mock the handler to raise ModelAlreadyExistsError
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks
            mock_is_admin.return_value = True
            mock_get_groups.return_value = ["admin-group"]
            mock_get_username.return_value = "test-admin"

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.side_effect = ModelAlreadyExistsError("Model 'existing-model' already exists")

            # Call the endpoint and expect HTTPException
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await create_model(create_request, mock_request)

            assert exc_info.value.status_code == 409

            # Verify request and failure logs exist
            event_types = [getattr(record, "event_type", None) for record in caplog.records]
            assert "CREATE_MODEL_REQUEST" in event_types
            assert "CREATE_MODEL_FAILURE" in event_types

            # Find the failure log and verify it contains error details
            failure_log = None
            for record in caplog.records:
                if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_FAILURE":
                    failure_log = record
                    break

            assert failure_log is not None
            assert failure_log.model_id == "existing-model"
            assert failure_log.username == "test-admin"
            assert "already exists" in failure_log.error

    @pytest.mark.asyncio
    async def test_create_model_extracts_real_ip_from_api_gateway_context(self, caplog):
        """Test that real client IP is extracted from API Gateway context, not headers."""
        # Setup mock request with API Gateway context
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "username": "test-admin",
                        "groups": json.dumps(["admin-group"]),
                        "authType": "JWT",
                    },
                    "identity": {
                        "sourceIp": "203.0.113.42",  # Real IP from API Gateway
                    },
                },
                "headers": {
                    "x-forwarded-for": "192.0.2.1, 198.51.100.1",  # User-provided, should be ignored
                },
            }
        }

        create_request = CreateModelRequest(
            modelId="test-model",
            modelName="test-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=True,
        )

        # Mock the handler and auth functions
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
            "utilities.auth.get_username"
        ) as mock_get_username, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks
            mock_is_admin.return_value = True
            mock_get_groups.return_value = ["admin-group"]
            mock_get_username.return_value = "test-admin"

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.return_value = MagicMock()

            # Call the endpoint
            await create_model(create_request, mock_request)

            # Find the CreateModel request log entry
            log_record = None
            for record in caplog.records:
                if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_REQUEST":
                    log_record = record
                    break

            assert log_record is not None

            # Verify the real IP from API Gateway context is used, not x-forwarded-for
            assert log_record.user["source_ip"] == "203.0.113.42"

            # Verify the user-provided x-forwarded-for is NOT in the log
            log_message = log_record.getMessage()
            assert "192.0.2.1" not in log_message
            assert "198.51.100.1" not in log_message

    @pytest.mark.asyncio
    async def test_create_model_handles_missing_event_context(self, caplog):
        """Test that logging handles missing API Gateway event context gracefully."""
        # Setup mock request WITHOUT aws.event
        mock_request = MagicMock(spec=Request)
        mock_request.scope = {}  # No aws.event

        create_request = CreateModelRequest(
            modelId="test-model",
            modelName="test-model-name",
            modelType=ModelType.TEXTGEN,
            streaming=True,
        )

        # Mock the handler and auth functions
        with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
            "utilities.auth.is_admin"
        ) as mock_is_admin, patch(
            "utilities.fastapi_middleware.auth_decorators.is_admin"
        ) as mock_decorator_is_admin, caplog.at_level(
            logging.INFO
        ):

            # Setup mocks - simulate admin with no event context
            mock_is_admin.return_value = True
            mock_decorator_is_admin.return_value = True

            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.return_value = MagicMock()

            # Call the endpoint
            await create_model(create_request, mock_request)

            # Find the CreateModel request log entry
            log_record = None
            for record in caplog.records:
                if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_REQUEST":
                    log_record = record
                    break

            assert log_record is not None

            # Verify default values are used when context is missing
            assert log_record.user["username"] == "unknown"
            assert log_record.user["auth_type"] == "unknown"
            assert log_record.user["source_ip"] == "unknown"

    @pytest.mark.asyncio
    async def test_create_model_extracts_registry_domain_from_various_formats(self, caplog):
        """Test that registry domain is correctly extracted from different image URL formats."""
        from models.domain_objects import InferenceContainer, LoadBalancerConfig, LoadBalancerHealthCheckConfig

        test_cases = [
            # (image_url, expected_domain)
            (
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-model:latest",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com",
            ),
            ("public.ecr.aws/my-repo/model:v1", "public.ecr.aws"),
            ("docker.io/library/nginx:latest", "docker.io"),
            ("https://registry.example.com/model:tag", "registry.example.com"),
            ("ghcr.io/org/repo:sha-abc123", "ghcr.io"),
            ("simple-name", "unknown"),  # No slash, returns "unknown"
        ]

        for image_url, expected_domain in test_cases:
            caplog.clear()

            # Setup mock request
            mock_request = MagicMock(spec=Request)
            mock_request.scope = {
                "aws.event": {
                    "requestContext": {
                        "authorizer": {
                            "username": "test-admin",
                            "groups": json.dumps(["admin-group"]),
                            "authType": "JWT",
                        },
                        "identity": {
                            "sourceIp": "192.168.1.100",
                        },
                    },
                }
            }

            # Create LISA-hosted model with all required fields
            create_request = CreateModelRequest(
                modelId="test-model",
                modelName="test-model-name",
                modelType=ModelType.TEXTGEN,
                streaming=True,
                instanceType="t2.micro",
                autoScalingConfig=AutoScalingConfig(
                    minCapacity=1,
                    maxCapacity=3,
                    desiredCapacity=2,
                    metricConfig=MetricConfig(
                        estimatedInstanceWarmup=60,
                        targetValue=60,
                        albMetricName="RequestCountPerTarget",
                        duration=60,
                    ),
                    cooldown=60,
                    defaultInstanceWarmup=60,
                ),
                containerConfig=ContainerConfig(
                    image=ContainerConfigImage(
                        baseImage=image_url,
                        type="custom",
                    ),
                    sharedMemorySize=1024,
                    healthCheckConfig=ContainerHealthCheckConfig(
                        command=["CMD", "test"],
                        interval=30,
                        startPeriod=60,
                        timeout=10,
                        retries=3,
                    ),
                ),
                loadBalancerConfig=LoadBalancerConfig(
                    healthCheckConfig=LoadBalancerHealthCheckConfig(
                        healthyThresholdCount=2,
                        unhealthyThresholdCount=2,
                        path="/health",
                        port="8080",
                        protocol="HTTP",
                        timeout=5,
                        interval=10,
                    )
                ),
                inferenceContainer=InferenceContainer.VLLM,
            )

            # Mock the handler and auth functions
            with patch("models.lambda_functions.CreateModelHandler") as mock_handler_class, patch(
                "utilities.fastapi_middleware.auth_decorators.is_admin"
            ) as mock_is_admin, patch("utilities.auth.get_groups") as mock_get_groups, patch(
                "utilities.auth.get_username"
            ) as mock_get_username, caplog.at_level(
                logging.INFO
            ):

                # Setup mocks
                mock_is_admin.return_value = True
                mock_get_groups.return_value = ["admin-group"]
                mock_get_username.return_value = "test-admin"

                mock_handler = MagicMock()
                mock_handler_class.return_value = mock_handler
                mock_handler.return_value = MagicMock()

                # Call the endpoint
                await create_model(create_request, mock_request)

                # Find the CreateModel request log entry
                log_record = None
                for record in caplog.records:
                    if hasattr(record, "event_type") and record.event_type == "CREATE_MODEL_REQUEST":
                        log_record = record
                        break

                assert log_record is not None, f"Log not found for image: {image_url}"
                actual_domain = log_record.container["registry_domain"]
                assert actual_domain == expected_domain, (
                    f"Expected domain '{expected_domain}' for image '{image_url}', " f"got '{actual_domain}'"
                )
