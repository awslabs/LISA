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

"""Unit tests for models lambda function."""

import json
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

import boto3
import pytest
from fastapi import HTTPException, Request
from models.domain_objects import (
    AutoScalingConfig,
    AutoScalingInstanceConfig,
    ContainerConfig,
    ContainerConfigImage,
    ContainerHealthCheckConfig,
    CreateModelRequest,
    CreateModelResponse,
    DeleteModelResponse,
    InferenceContainer,
    LISAModel,
    LoadBalancerConfig,
    LoadBalancerHealthCheckConfig,
    MetricConfig,
    ModelStatus,
    ModelType,
    UpdateModelRequest,
    UpdateModelResponse,
)
from models.exception import (
    InvalidStateTransitionError,
    ModelAlreadyExistsError,
    ModelInUseError,
    ModelNotFoundError,
)
from models.handler.base_handler import BaseApiHandler
from models.handler.create_model_handler import CreateModelHandler
from models.handler.delete_model_handler import DeleteModelHandler
from models.handler.get_model_handler import GetModelHandler
from models.handler.list_models_handler import ListModelsHandler
from models.handler.update_model_handler import UpdateModelHandler
from models.handler.utils import to_lisa_model
from models.lambda_functions import (
    app,
    create_model,
    delete_model,
    get_admin_status_and_groups,
    get_instances,
    model_not_found_handler,
    update_model,
    user_error_handler,
    validation_exception_handler,
)
from moto import mock_aws


# Fixtures for testing
@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    context = MagicMock()
    context.function_name = "model-lambda"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:model-lambda"
    context.memory_limit_in_mb = 128
    context.log_group_name = "/aws/lambda/model-lambda"
    context.log_stream_name = "2023/01/01/[$LATEST]abcdef123456"
    context.aws_request_id = "00000000-0000-0000-0000-000000000000"
    return context


@pytest.fixture
def dynamodb():
    """Mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture
def model_table(dynamodb):
    """Create mock model table."""
    table = dynamodb.create_table(
        TableName="model-table",
        KeySchema=[{"AttributeName": "model_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "model_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return table


@pytest.fixture
def guardrails_table(dynamodb):
    """Create mock guardrails table."""
    table = dynamodb.create_table(
        TableName="guardrails-table",
        KeySchema=[
            {"AttributeName": "guardrailId", "KeyType": "HASH"},
            {"AttributeName": "modelId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "guardrailId", "AttributeType": "S"},
            {"AttributeName": "modelId", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "ModelIdIndex",
                "KeySchema": [
                    {"AttributeName": "modelId", "KeyType": "HASH"},
                    {"AttributeName": "guardrailId", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return table


@pytest.fixture
def sample_model():
    """Create a sample model dictionary."""
    return {
        "model_id": "test-model",
        "auto_scaling_group": "test-asg",
        "model_status": ModelStatus.IN_SERVICE,
        "last_modified_date": int(1747689448),
        "model_config": {
            "modelId": "test-model",
            "modelName": "gpt-3.5-turbo",
            "modelType": ModelType.TEXTGEN,
            "streaming": True,
            "features": [{"name": "test-feature", "overview": "This is a test feature"}],
        },
    }


@pytest.fixture
def mock_stepfunctions_client():
    """Mock Step Functions client."""
    client = MagicMock()
    client.start_execution.return_value = {
        "executionArn": "arn:aws:states:us-east-1:123456789012:execution:CreateModelStateMachine:test-execution",
        "startDate": "2025-05-19T00:00:00.000000Z",
    }
    return client


@pytest.fixture
def mock_autoscaling_client():
    """Mock AutoScaling client."""
    client = MagicMock()
    client.describe_auto_scaling_groups.return_value = {
        "AutoScalingGroups": [{"AutoScalingGroupName": "test-asg", "MinSize": 1, "MaxSize": 3, "DesiredCapacity": 2}]
    }
    return client


def test_to_lisa_model():
    """Test the to_lisa_model utility function."""
    # Test with minimal model data
    model_dict = {
        "model_config": {
            "modelId": "test-model",
            "modelName": "test-model-name",
            "modelType": ModelType.TEXTGEN,
            "streaming": True,
        },
        "model_status": ModelStatus.CREATING,
    }

    result = to_lisa_model(model_dict)
    assert isinstance(result, LISAModel)
    assert result.modelId == "test-model"
    assert result.modelName == "test-model-name"
    assert result.modelType == ModelType.TEXTGEN
    assert result.status == ModelStatus.CREATING
    assert result.streaming is True

    # Test with model URL
    model_dict_with_url = {
        "model_config": {
            "modelId": "test-model",
            "modelName": "test-model-name",
            "modelType": ModelType.TEXTGEN,
            "streaming": True,
        },
        "model_status": ModelStatus.CREATING,
        "model_url": "https://example.com/model",
    }

    result_with_url = to_lisa_model(model_dict_with_url)
    assert result_with_url.modelUrl == "https://example.com/model"


def test_base_api_handler():
    """Test BaseApiHandler initialization."""
    model_table = MagicMock()
    guardrails_table = MagicMock()
    autoscaling_client = MagicMock()
    stepfunctions_client = MagicMock()

    handler = BaseApiHandler(
        model_table_resource=model_table,
        autoscaling_client=autoscaling_client,
        stepfunctions_client=stepfunctions_client,
        guardrails_table_resource=guardrails_table,
    )

    assert handler._model_table == model_table
    assert handler._autoscaling == autoscaling_client
    assert handler._stepfunctions == stepfunctions_client
    assert handler._guardrails_table == guardrails_table


def test_create_model_handler(mock_stepfunctions_client, model_table, mock_autoscaling_client, guardrails_table):
    """Test CreateModelHandler.__call__ method."""
    # Create handler instance
    handler = CreateModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Create a request
    request = CreateModelRequest(
        modelId="test-model", modelName="test-model", modelType=ModelType.TEXTGEN, streaming=True
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, CreateModelResponse)
    assert response.model.modelId == "test-model"
    assert response.model.modelName == "test-model"
    assert response.model.modelType == ModelType.TEXTGEN
    assert response.model.status == ModelStatus.CREATING
    assert response.model.streaming is True

    # Test with existing model
    model_table.put_item(
        Item={
            "model_id": "existing-model",
            "model_config": {
                "modelId": "existing-model",
                "modelName": "existing-model",
                "modelType": ModelType.TEXTGEN,
                "streaming": True,
            },
            "model_status": ModelStatus.IN_SERVICE,
        }
    )

    request.modelId = "existing-model"
    with pytest.raises(ModelAlreadyExistsError, match="Model 'existing-model' already exists"):
        handler(request)


def test_create_model_validation(mock_autoscaling_client, mock_stepfunctions_client, model_table, guardrails_table):
    """Test validation in CreateModelHandler."""
    # Create handler instance
    handler = CreateModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Create a request with containerConfig, autoScalingConfig, and loadBalancerConfig
    request = CreateModelRequest(
        modelId="test-validation-model",
        modelName="test-model",
        modelType=ModelType.TEXTGEN,
        streaming=True,
        containerConfig=ContainerConfig(
            image=ContainerConfigImage(baseImage="test-image:latest", type="test-type"),
            sharedMemorySize=1024,
            healthCheckConfig=ContainerHealthCheckConfig(
                command=["CMD", "test", "command"], interval=30, startPeriod=60, timeout=10, retries=3
            ),
        ),
        autoScalingConfig=AutoScalingConfig(
            minCapacity=1,
            maxCapacity=3,
            desiredCapacity=2,
            metricConfig=MetricConfig(
                estimatedInstanceWarmup=60, targetValue=60, albMetricName="RequestCountPerTarget", duration=60
            ),
            cooldown=60,
            defaultInstanceWarmup=60,
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
        instanceType="t2.micro",
    )

    # Call validate method
    handler.validate(request)

    # Should not raise exceptions


def test_delete_model_handler(
    mock_stepfunctions_client, model_table, sample_model, mock_autoscaling_client, guardrails_table
):
    """Test DeleteModelHandler.__call__ method."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create handler instance
    handler = DeleteModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Mock SSM client, VectorStoreRepository, and CollectionRepository
    with patch("models.handler.delete_model_handler.ssm_client") as mock_ssm, patch(
        "models.handler.delete_model_handler.VectorStoreRepository"
    ) as mock_repo_class, patch(
        "models.handler.delete_model_handler.CollectionRepository"
    ) as mock_collection_repo_class:
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "vector-store-table"}}

        mock_repo = mock_repo_class.return_value
        mock_repo.find_repositories_using_model.return_value = []

        mock_collection_repo = mock_collection_repo_class.return_value
        mock_collection_repo.find_collections_using_model.return_value = []

        # Call handler
        response = handler("test-model")

        # Verify response
        assert isinstance(response.model, LISAModel)
        assert response.model.modelId == "test-model"

        # Verify the repositories were checked
        mock_repo.find_repositories_using_model.assert_called_once_with("test-model")
        mock_collection_repo.find_collections_using_model.assert_called_once_with("test-model")

    # Test with non-existent model
    with pytest.raises(ModelNotFoundError, match="Model 'non-existent-model' was not found"):
        handler("non-existent-model")


def test_delete_model_handler_model_in_use_by_repository(
    mock_stepfunctions_client, model_table, sample_model, mock_autoscaling_client, guardrails_table
):
    """Test DeleteModelHandler raises error when model is in use by repository."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create handler instance
    handler = DeleteModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Mock SSM client, VectorStoreRepository, and CollectionRepository
    with patch("models.handler.delete_model_handler.ssm_client") as mock_ssm, patch(
        "models.handler.delete_model_handler.VectorStoreRepository"
    ) as mock_repo_class, patch(
        "models.handler.delete_model_handler.CollectionRepository"
    ) as mock_collection_repo_class:
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "vector-store-table"}}

        mock_repo = mock_repo_class.return_value
        mock_repo.find_repositories_using_model.return_value = [
            {"repository_id": "test-repo", "usage_type": "repository"}
        ]

        mock_collection_repo = mock_collection_repo_class.return_value
        mock_collection_repo.find_collections_using_model.return_value = []

        # Call handler and expect error
        with pytest.raises(
            ModelInUseError,
            match="Model 'test-model' is currently in use by: repository",
        ):
            handler("test-model")

        # Verify the repositories were checked
        mock_repo.find_repositories_using_model.assert_called_once_with("test-model")
        mock_collection_repo.find_collections_using_model.assert_called_once_with("test-model")


def test_delete_model_handler_model_in_use_by_pipeline(
    mock_stepfunctions_client, model_table, sample_model, mock_autoscaling_client, guardrails_table
):
    """Test DeleteModelHandler raises error when model is in use by pipeline."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create handler instance
    handler = DeleteModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Mock SSM client, VectorStoreRepository, and CollectionRepository
    with patch("models.handler.delete_model_handler.ssm_client") as mock_ssm, patch(
        "models.handler.delete_model_handler.VectorStoreRepository"
    ) as mock_repo_class, patch(
        "models.handler.delete_model_handler.CollectionRepository"
    ) as mock_collection_repo_class:
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "vector-store-table"}}

        mock_repo = mock_repo_class.return_value
        mock_repo.find_repositories_using_model.return_value = [
            {"repository_id": "test-repo", "usage_type": "pipeline"}
        ]

        mock_collection_repo = mock_collection_repo_class.return_value
        mock_collection_repo.find_collections_using_model.return_value = []

        # Call handler and expect error
        with pytest.raises(
            ModelInUseError,
            match="Model 'test-model' is currently in use by: repository",
        ):
            handler("test-model")

        # Verify the repositories were checked
        mock_repo.find_repositories_using_model.assert_called_once_with("test-model")
        mock_collection_repo.find_collections_using_model.assert_called_once_with("test-model")


def test_delete_model_handler_without_vector_store_table(
    mock_stepfunctions_client, model_table, sample_model, mock_autoscaling_client, guardrails_table
):
    """Test DeleteModelHandler works when RAG is not deployed (SSM parameter not found)."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create handler instance
    handler = DeleteModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Mock SSM client to raise ParameterNotFound
    with patch("models.handler.delete_model_handler.ssm_client") as mock_ssm:
        from botocore.exceptions import ClientError

        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Parameter not found"}}, "GetParameter"
        )

        # Call handler - should succeed without checking vector store
        response = handler("test-model")

        # Verify response
        assert isinstance(response.model, LISAModel)
        assert response.model.modelId == "test-model"

        # Verify state machine was called
        mock_stepfunctions_client.start_execution.assert_called_once()


def test_get_model_handler(
    model_table, sample_model, mock_autoscaling_client, mock_stepfunctions_client, guardrails_table
):
    """Test GetModelHandler.__call__ method."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create handler instance
    handler = GetModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Call handler
    response = handler("test-model")

    # Verify response
    assert isinstance(response.model, LISAModel)
    assert response.model.modelId == "test-model"

    # Test with non-existent model
    with pytest.raises(ModelNotFoundError, match="Model 'non-existent-model' was not found"):
        handler("non-existent-model")


def test_list_models_handler(
    model_table, sample_model, mock_autoscaling_client, mock_stepfunctions_client, guardrails_table
):
    """Test ListModelsHandler.__call__ method."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create another model
    another_model = sample_model.copy()
    another_model["model_id"] = "another-model"
    another_model["model_config"]["modelId"] = "another-model"
    model_table.put_item(Item=another_model)

    # Create handler instance
    handler = ListModelsHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Call handler
    response = handler()

    # Verify response
    assert len(response.models) == 2
    model_ids = [model.modelId for model in response.models]
    assert "test-model" in model_ids
    assert "another-model" in model_ids


def test_update_model_handler(
    model_table, mock_autoscaling_client, mock_stepfunctions_client, sample_model, guardrails_table
):
    """Test UpdateModelHandler.__call__ method."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create model with STOPPED status for testing
    stopped_model = sample_model.copy()
    stopped_model["model_id"] = "stopped-model"
    stopped_model["model_config"]["modelId"] = "stopped-model"
    stopped_model["model_status"] = ModelStatus.STOPPED
    model_table.put_item(Item=stopped_model)

    # Create handler instance
    handler = UpdateModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Mock the to_lisa_model function to return a model with streaming=False
    with patch("models.handler.update_model_handler.to_lisa_model") as mock_to_lisa_model, patch.object(
        handler, "_stepfunctions"
    ) as mock_sf:
        # Configure the mock to return a model with streaming=False
        mock_model = LISAModel(
            modelId="test-model",
            modelName="gpt-3.5-turbo",
            modelType=ModelType.TEXTGEN,
            status=ModelStatus.IN_SERVICE,
            streaming=False,
            features=[{"name": "test-feature", "overview": "This is a test feature"}],
        )
        mock_to_lisa_model.return_value = mock_model

        mock_sf.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:UpdateModelStateMachine:test-execution",
            "startDate": "2025-05-19T00:00:00.000000Z",
        }

        # Test update model metadata
        response = handler("test-model", UpdateModelRequest(streaming=False))

        # Verify response
        assert isinstance(response.model, LISAModel)
        assert response.model.modelId == "test-model"
        assert response.model.streaming is False

        # Reset the mock for the next test
        mock_to_lisa_model.reset_mock()

        # Configure the mock for the enable test
        mock_model_enabled = LISAModel(
            modelId="stopped-model",
            modelName="gpt-3.5-turbo",
            modelType=ModelType.TEXTGEN,
            status=ModelStatus.STARTING,
            streaming=True,
            features=[{"name": "test-feature", "overview": "This is a test feature"}],
        )
        mock_to_lisa_model.return_value = mock_model_enabled

        # Test enable model
        response = handler("stopped-model", UpdateModelRequest(enabled=True))
        assert response.model.modelId == "stopped-model"
        assert response.model.status == ModelStatus.STARTING

        # Test with non-existent model
        mock_model_table = MagicMock()
        mock_model_table.get_item.return_value = {"Item": None}
        handler._model_table = mock_model_table

        with pytest.raises(ModelNotFoundError, match="Model 'non-existent-model' was not found"):
            handler("non-existent-model", UpdateModelRequest(streaming=False))


def test_update_model_validation(
    model_table, mock_autoscaling_client, mock_stepfunctions_client, sample_model, guardrails_table
):
    """Test validation in UpdateModelHandler."""
    # Add sample model to table
    model_table.put_item(Item=sample_model)

    # Create model with STOPPED status for testing
    stopped_model = sample_model.copy()
    stopped_model["model_id"] = "stopped-model"
    stopped_model["model_config"]["modelId"] = "stopped-model"
    stopped_model["model_status"] = ModelStatus.STOPPED
    model_table.put_item(Item=stopped_model)

    # Create model with CREATING status for testing
    creating_model = sample_model.copy()
    creating_model["model_id"] = "creating-model"
    creating_model["model_config"]["modelId"] = "creating-model"
    creating_model["model_status"] = ModelStatus.CREATING
    model_table.put_item(Item=creating_model)

    # Create handler instance
    handler = UpdateModelHandler(
        autoscaling_client=mock_autoscaling_client,
        stepfunctions_client=mock_stepfunctions_client,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    # Test validation for model in invalid state
    with pytest.raises(InvalidStateTransitionError, match="Model cannot be updated when it is not in the"):
        handler("creating-model", UpdateModelRequest(streaming=False))

    # Test with invalid enabled state transition (enable already enabled model)
    with pytest.raises(InvalidStateTransitionError, match="Model cannot be enabled when it is not in the"):
        handler("test-model", UpdateModelRequest(enabled=True))

    # Test with invalid enabled state transition (disable already stopped model)
    with pytest.raises(InvalidStateTransitionError, match="Model cannot be stopped when it is not in the"):
        handler("stopped-model", UpdateModelRequest(enabled=False))

    # Test with simultaneous enabled and autoScalingInstanceConfig
    with pytest.raises(
        ValueError, match="Start or Stop operations and AutoScaling changes must happen in separate requests"
    ):
        handler(
            "test-model",
            UpdateModelRequest(enabled=False, autoScalingInstanceConfig=AutoScalingInstanceConfig(minCapacity=1)),
        )

    # Test with non-LISA hosted model
    non_lisa_model = sample_model.copy()
    non_lisa_model["model_id"] = "non-lisa-model"
    non_lisa_model["model_config"]["modelId"] = "non-lisa-model"
    non_lisa_model.pop("auto_scaling_group", None)
    model_table.put_item(Item=non_lisa_model)

    with pytest.raises(
        ValueError, match="Cannot update AutoScaling Config for model not hosted in LISA infrastructure"
    ):
        handler(
            "non-lisa-model", UpdateModelRequest(autoScalingInstanceConfig=AutoScalingInstanceConfig(minCapacity=1))
        )

    # Test with desiredCapacity > maxCapacity
    with pytest.raises(ValueError, match="Desired capacity cannot exceed ASG max"):
        handler(
            "test-model", UpdateModelRequest(autoScalingInstanceConfig=AutoScalingInstanceConfig(desiredCapacity=5))
        )


@pytest.mark.asyncio
async def test_exception_handlers():
    """Test exception handlers."""
    from fastapi.encoders import jsonable_encoder
    from fastapi.exceptions import RequestValidationError

    # Setup mock request
    request = MagicMock()

    # Test ModelNotFoundError handler
    exc = ModelNotFoundError("Model not found")
    response = await model_not_found_handler(request, exc)
    assert response.status_code == 404
    assert json.loads(response.body)["detail"] == "Model not found"

    # Test RequestValidationError handler
    mock_errors = [{"loc": ["body", "modelId"], "msg": "field required", "type": "value_error.missing"}]
    exc = MagicMock(spec=RequestValidationError)
    exc.errors.return_value = mock_errors
    response = await validation_exception_handler(request, exc)
    assert response.status_code == 422
    assert json.loads(response.body)["detail"] == jsonable_encoder(mock_errors)
    assert json.loads(response.body)["type"] == "RequestValidationError"

    # Test user error handler with ModelAlreadyExistsError
    exc = ModelAlreadyExistsError("Model already exists")
    response = await user_error_handler(request, exc)
    assert response.status_code == 400
    assert json.loads(response.body)["detail"] == "Model already exists"

    # Test user error handler with ValueError
    exc = ValueError("Invalid value")
    response = await user_error_handler(request, exc)
    assert response.status_code == 400
    assert json.loads(response.body)["detail"] == "Invalid value"


@pytest.mark.asyncio
async def test_fastapi_endpoints(sample_model, model_table, mock_autoscaling_client, mock_stepfunctions_client):
    """Test FastAPI endpoints."""
    from fastapi.testclient import TestClient

    # Create test client
    client = TestClient(app)

    # Setup mocks for the handlers
    with patch("models.lambda_functions.CreateModelHandler") as mock_create_handler, patch(
        "models.lambda_functions.ListModelsHandler"
    ) as mock_list_handler, patch("models.lambda_functions.GetModelHandler") as mock_get_handler, patch(
        "models.lambda_functions.UpdateModelHandler"
    ) as mock_update_handler, patch(
        "models.lambda_functions.DeleteModelHandler"
    ) as mock_delete_handler, patch(
        "models.lambda_functions.get_admin_status_and_groups"
    ) as mock_get_admin_status:
        # Mock admin status - return admin=True for all operations in this test
        mock_get_admin_status.return_value = (True, [])

        # Setup handler mocks
        create_handler_instance = MagicMock()
        create_model_response = CreateModelResponse(
            model=LISAModel(
                modelId="new-model",
                modelName="new-model-name",
                modelType=ModelType.TEXTGEN,
                status=ModelStatus.CREATING,
                streaming=True,
            )
        )
        create_handler_instance.return_value = create_model_response
        mock_create_handler.return_value = create_handler_instance

        list_handler_instance = MagicMock()
        list_models_response = {
            "models": [
                LISAModel(
                    modelId="existing-model",
                    modelName="existing-model-name",
                    modelType=ModelType.TEXTGEN,
                    status=ModelStatus.IN_SERVICE,
                    streaming=True,
                )
            ]
        }
        list_handler_instance.return_value = list_models_response
        mock_list_handler.return_value = list_handler_instance

        get_handler_instance = MagicMock()
        get_model_response = {
            "model": LISAModel(
                modelId="existing-model",
                modelName="existing-model-name",
                modelType=ModelType.TEXTGEN,
                status=ModelStatus.IN_SERVICE,
                streaming=True,
            )
        }
        get_handler_instance.return_value = get_model_response
        mock_get_handler.return_value = get_handler_instance

        update_handler_instance = MagicMock()
        update_model_response = {
            "model": LISAModel(
                modelId="existing-model",
                modelName="existing-model-name",
                modelType=ModelType.TEXTGEN,
                status=ModelStatus.IN_SERVICE,
                streaming=False,
            )
        }
        update_handler_instance.return_value = update_model_response
        mock_update_handler.return_value = update_handler_instance

        delete_handler_instance = MagicMock()
        delete_model_response = {
            "model": LISAModel(
                modelId="existing-model",
                modelName="existing-model-name",
                modelType=ModelType.TEXTGEN,
                status=ModelStatus.DELETING,
                streaming=True,
            )
        }
        delete_handler_instance.return_value = delete_model_response
        mock_delete_handler.return_value = delete_handler_instance

        # Test create_model endpoint
        create_request_data = {
            "modelId": "test-model",
            "modelName": "test-model",
            "modelType": "textgen",
            "streaming": True,
        }
        response = client.post("/", json=create_request_data)
        assert response.status_code == 200
        assert "model" in response.json()
        assert response.json()["model"]["modelId"] == "new-model"
        mock_create_handler.assert_called_once()

        # Test list_models endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert "models" in response.json()
        assert len(response.json()["models"]) == 1
        assert response.json()["models"][0]["modelId"] == "existing-model"
        mock_list_handler.assert_called_once()

        # Test get_model endpoint
        response = client.get("/existing-model")
        assert response.status_code == 200
        assert "model" in response.json()
        assert response.json()["model"]["modelId"] == "existing-model"
        mock_get_handler.assert_called_once()

        # Test update_model endpoint
        update_request_data = {"streaming": False}
        response = client.put("/existing-model", json=update_request_data)
        assert response.status_code == 200
        assert "model" in response.json()
        assert response.json()["model"]["streaming"] is False
        mock_update_handler.assert_called_once()

        # Test delete_model endpoint
        response = client.delete("/existing-model")
        assert response.status_code == 200
        assert "model" in response.json()
        assert response.json()["model"]["status"] == "Deleting"
        mock_delete_handler.assert_called_once()


@pytest.mark.asyncio
async def test_get_instances():
    """Test get_instances endpoint."""

    # Mock the shape_for method to return a mock with enum attribute
    mock_shape = MagicMock()
    mock_shape.enum = ["t2.micro", "t3.small", "m5.large"]

    with patch("models.lambda_functions.sess") as mock_sess:
        mock_sess.get_service_model.return_value.shape_for.return_value = mock_shape

        # Test the endpoint
        result = await get_instances()

        # Verify the result
        assert isinstance(result, list)
        assert "t2.micro" in result
        assert "t3.small" in result
        assert "m5.large" in result


@pytest.fixture
def admin_event():
    """Create an AWS event with admin user."""
    return {
        "requestContext": {
            "authorizer": {
                "username": "admin-user",
                "groups": json.dumps(["admin-group"]),
            }
        }
    }


@pytest.fixture
def non_admin_event():
    """Create an AWS event with non-admin user."""
    return {
        "requestContext": {
            "authorizer": {
                "username": "regular-user",
                "groups": json.dumps(["user-group"]),
            }
        }
    }


@pytest.mark.asyncio
async def test_get_admin_status_and_groups():
    """Test the get_admin_status_and_groups helper function."""

    # Test with admin event
    admin_event = {
        "requestContext": {
            "authorizer": {
                "username": "admin-user",
                "groups": json.dumps(["admin-group"]),
            }
        }
    }

    mock_request = MagicMock(spec=Request)
    mock_request.scope = {"aws.event": admin_event}

    with patch("models.lambda_functions.is_admin") as mock_is_admin, patch(
        "models.lambda_functions.get_groups"
    ) as mock_get_groups:
        mock_is_admin.return_value = True
        mock_get_groups.return_value = ["admin-group"]

        admin_status, user_groups = get_admin_status_and_groups(mock_request)
        assert admin_status is True
        assert user_groups == ["admin-group"]

    # Test with non-admin event
    non_admin_event = {
        "requestContext": {
            "authorizer": {
                "username": "regular-user",
                "groups": json.dumps(["user-group"]),
            }
        }
    }

    mock_request.scope = {"aws.event": non_admin_event}

    with patch("models.lambda_functions.is_admin") as mock_is_admin, patch(
        "models.lambda_functions.get_groups"
    ) as mock_get_groups:
        mock_is_admin.return_value = False
        mock_get_groups.return_value = ["user-group"]

        admin_status, user_groups = get_admin_status_and_groups(mock_request)
        assert admin_status is False
        assert user_groups == ["user-group"]

    # Test with no event in scope
    mock_request.scope = {}
    admin_status, user_groups = get_admin_status_and_groups(mock_request)
    assert admin_status is False
    assert user_groups == []


@pytest.mark.asyncio
async def test_create_model_admin_required(
    sample_model, model_table, mock_autoscaling_client, mock_stepfunctions_client, admin_event, non_admin_event
):
    """Test that create_model endpoint requires admin access."""

    # Test non-admin cannot create
    mock_request = MagicMock(spec=Request)
    mock_request.scope = {"aws.event": non_admin_event}

    create_request = CreateModelRequest(
        modelId="test-model", modelName="test-model", modelType=ModelType.TEXTGEN, streaming=True
    )

    with patch("models.lambda_functions.is_admin") as mock_is_admin, patch(
        "models.lambda_functions.get_groups"
    ) as mock_get_groups:
        mock_is_admin.return_value = False
        mock_get_groups.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await create_model(create_request, mock_request)
        assert exc_info.value.status_code == 403
        assert "User does not have permission to create models" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_update_model_admin_required(
    sample_model, model_table, mock_autoscaling_client, mock_stepfunctions_client, admin_event, non_admin_event
):
    """Test that update_model endpoint requires admin access."""

    # Test non-admin cannot update
    mock_request = MagicMock(spec=Request)
    mock_request.scope = {"aws.event": non_admin_event}

    update_request = UpdateModelRequest(streaming=False)

    with patch("models.lambda_functions.is_admin") as mock_is_admin, patch(
        "models.lambda_functions.get_groups"
    ) as mock_get_groups:
        mock_is_admin.return_value = False
        mock_get_groups.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await update_model("test-model", update_request, mock_request)
        assert exc_info.value.status_code == 403
        assert "User does not have permission to update models" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_delete_model_admin_required(
    sample_model, model_table, mock_autoscaling_client, mock_stepfunctions_client, admin_event, non_admin_event
):
    """Test that delete_model endpoint requires admin access."""

    # Test non-admin cannot delete
    mock_request = MagicMock(spec=Request)
    mock_request.scope = {"aws.event": non_admin_event}

    with patch("models.lambda_functions.is_admin") as mock_is_admin, patch(
        "models.lambda_functions.get_groups"
    ) as mock_get_groups:
        mock_is_admin.return_value = False
        mock_get_groups.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await delete_model("test-model", mock_request)
        assert exc_info.value.status_code == 403
        assert "User does not have permission to delete models" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_create_update_delete_admin_allowed(
    sample_model, model_table, mock_autoscaling_client, mock_stepfunctions_client, admin_event
):
    """Test that admin users can successfully create, update, and delete models."""

    mock_request = MagicMock(spec=Request)
    mock_request.scope = {"aws.event": admin_event}

    with patch("models.lambda_functions.is_admin") as mock_is_admin, patch(
        "models.lambda_functions.get_groups"
    ) as mock_get_groups, patch("models.lambda_functions.CreateModelHandler") as mock_create_handler, patch(
        "models.lambda_functions.UpdateModelHandler"
    ) as mock_update_handler, patch(
        "models.lambda_functions.DeleteModelHandler"
    ) as mock_delete_handler:
        mock_is_admin.return_value = True
        mock_get_groups.return_value = ["admin-group"]

        # Mock create handler
        create_handler_instance = MagicMock()
        create_model_response = CreateModelResponse(
            model=LISAModel(
                modelId="new-model",
                modelName="new-model-name",
                modelType=ModelType.TEXTGEN,
                status=ModelStatus.CREATING,
                streaming=True,
            )
        )
        create_handler_instance.return_value = create_model_response
        mock_create_handler.return_value = create_handler_instance

        # Test admin can create
        create_request = CreateModelRequest(
            modelId="test-model", modelName="test-model", modelType=ModelType.TEXTGEN, streaming=True
        )
        response = await create_model(create_request, mock_request)
        assert isinstance(response, CreateModelResponse)
        assert response.model.modelId == "new-model"

        # Mock update handler
        model_table.put_item(Item=sample_model)
        update_handler_instance = MagicMock()
        update_model_response = UpdateModelResponse(
            model=LISAModel(
                modelId="test-model",
                modelName="gpt-3.5-turbo",
                modelType=ModelType.TEXTGEN,
                status=ModelStatus.IN_SERVICE,
                streaming=False,
                features=[{"name": "test-feature", "overview": "This is a test feature"}],
            )
        )
        update_handler_instance.return_value = update_model_response
        mock_update_handler.return_value = update_handler_instance

        # Test admin can update
        update_request = UpdateModelRequest(streaming=False)
        response = await update_model("test-model", update_request, mock_request)
        assert isinstance(response, UpdateModelResponse)
        assert response.model.modelId == "test-model"

        # Mock delete handler
        delete_handler_instance = MagicMock()
        delete_model_response = DeleteModelResponse(
            model=LISAModel(
                modelId="test-model",
                modelName="gpt-3.5-turbo",
                modelType=ModelType.TEXTGEN,
                status=ModelStatus.DELETING,
                streaming=True,
                features=[{"name": "test-feature", "overview": "This is a test feature"}],
            )
        )
        delete_handler_instance.return_value = delete_model_response
        mock_delete_handler.return_value = delete_handler_instance

        # Test admin can delete
        response = await delete_model("test-model", mock_request)
        assert isinstance(response, DeleteModelResponse)
        assert response.model.modelId == "test-model"
        assert response.model.status == ModelStatus.DELETING
