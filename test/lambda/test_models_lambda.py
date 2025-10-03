"""Test module for models lambda functions - refactored version using fixture-based mocking."""

import json
import os
import pytest
from unittest.mock import MagicMock, patch
from moto import mock_aws
import boto3


@pytest.fixture
def mock_models_common():
    """Common mocks for models lambda functions."""
    
    # Set up environment variables
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "MODEL_TABLE_NAME": "model-table",
        "CREATE_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:CreateModelStateMachine",
        "DELETE_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:DeleteModelStateMachine",
        "UPDATE_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:UpdateModelStateMachine",
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def models_functions(mock_models_common):
    """Import models lambda functions and classes with mocked dependencies."""
    from models.domain_objects import (
        AutoScalingConfig,
        AutoScalingInstanceConfig,
        ContainerConfig,
        ContainerConfigImage,
        ContainerHealthCheckConfig,
        CreateModelRequest,
        CreateModelResponse,
        InferenceContainer,
        LISAModel,
        LoadBalancerConfig,
        LoadBalancerHealthCheckConfig,
        MetricConfig,
        ModelStatus,
        ModelType,
        UpdateModelRequest,
    )
    from models.exception import InvalidStateTransitionError, ModelAlreadyExistsError, ModelNotFoundError
    from models.handler.base_handler import BaseApiHandler
    from models.handler.create_model_handler import CreateModelHandler
    from models.handler.delete_model_handler import DeleteModelHandler
    from models.handler.get_model_handler import GetModelHandler
    from models.handler.list_models_handler import ListModelsHandler
    from models.handler.update_model_handler import UpdateModelHandler
    from models.handler.utils import to_lisa_model
    
    return {
        "domain_objects": {
            "AutoScalingConfig": AutoScalingConfig,
            "AutoScalingInstanceConfig": AutoScalingInstanceConfig,
            "ContainerConfig": ContainerConfig,
            "ContainerConfigImage": ContainerConfigImage,
            "ContainerHealthCheckConfig": ContainerHealthCheckConfig,
            "CreateModelRequest": CreateModelRequest,
            "CreateModelResponse": CreateModelResponse,
            "InferenceContainer": InferenceContainer,
            "LISAModel": LISAModel,
            "LoadBalancerConfig": LoadBalancerConfig,
            "LoadBalancerHealthCheckConfig": LoadBalancerHealthCheckConfig,
            "MetricConfig": MetricConfig,
            "ModelStatus": ModelStatus,
            "ModelType": ModelType,
            "UpdateModelRequest": UpdateModelRequest,
        },
        "exceptions": {
            "InvalidStateTransitionError": InvalidStateTransitionError,
            "ModelAlreadyExistsError": ModelAlreadyExistsError,
            "ModelNotFoundError": ModelNotFoundError,
        },
        "handlers": {
            "BaseApiHandler": BaseApiHandler,
            "CreateModelHandler": CreateModelHandler,
            "DeleteModelHandler": DeleteModelHandler,
            "GetModelHandler": GetModelHandler,
            "ListModelsHandler": ListModelsHandler,
            "UpdateModelHandler": UpdateModelHandler,
        },
        "utils": {
            "to_lisa_model": to_lisa_model,
        }
    }


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
def dynamodb_table():
    """Create mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="model-table",
            KeySchema=[{"AttributeName": "model_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "model_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


@pytest.fixture
def sample_model(models_functions):
    """Create a sample model dictionary."""
    ModelStatus = models_functions["domain_objects"]["ModelStatus"]
    ModelType = models_functions["domain_objects"]["ModelType"]
    
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


class TestModelUtils:
    """Test class for model utilities."""
    
    def test_to_lisa_model(self, models_functions):
        """Test the to_lisa_model utility function."""
        to_lisa_model = models_functions["utils"]["to_lisa_model"]
        LISAModel = models_functions["domain_objects"]["LISAModel"]
        ModelType = models_functions["domain_objects"]["ModelType"]
        ModelStatus = models_functions["domain_objects"]["ModelStatus"]
        
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


class TestBaseApiHandler:
    """Test class for BaseApiHandler."""
    
    def test_base_api_handler(self, models_functions):
        """Test BaseApiHandler initialization."""
        BaseApiHandler = models_functions["handlers"]["BaseApiHandler"]
        
        model_table = MagicMock()
        autoscaling_client = MagicMock()
        stepfunctions_client = MagicMock()

        handler = BaseApiHandler(
            model_table_resource=model_table,
            autoscaling_client=autoscaling_client,
            stepfunctions_client=stepfunctions_client,
        )

        assert handler._model_table == model_table
        assert handler._autoscaling == autoscaling_client
        assert handler._stepfunctions == stepfunctions_client


class TestCreateModelHandler:
    """Test class for CreateModelHandler."""
    
    def test_create_model_handler(self, models_functions, mock_stepfunctions_client, 
                                 dynamodb_table, mock_autoscaling_client):
        """Test CreateModelHandler.__call__ method."""
        CreateModelHandler = models_functions["handlers"]["CreateModelHandler"]
        CreateModelRequest = models_functions["domain_objects"]["CreateModelRequest"]
        CreateModelResponse = models_functions["domain_objects"]["CreateModelResponse"]
        ModelType = models_functions["domain_objects"]["ModelType"]
        ModelStatus = models_functions["domain_objects"]["ModelStatus"]
        ModelAlreadyExistsError = models_functions["exceptions"]["ModelAlreadyExistsError"]
        
        # Create handler instance
        handler = CreateModelHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=dynamodb_table,
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
        dynamodb_table.put_item(
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

    def test_create_model_validation(self, models_functions, mock_autoscaling_client, 
                                    mock_stepfunctions_client, dynamodb_table):
        """Test validation in CreateModelHandler."""
        CreateModelHandler = models_functions["handlers"]["CreateModelHandler"]
        CreateModelRequest = models_functions["domain_objects"]["CreateModelRequest"]
        ModelType = models_functions["domain_objects"]["ModelType"]
        ContainerConfig = models_functions["domain_objects"]["ContainerConfig"]
        ContainerConfigImage = models_functions["domain_objects"]["ContainerConfigImage"]
        ContainerHealthCheckConfig = models_functions["domain_objects"]["ContainerHealthCheckConfig"]
        AutoScalingConfig = models_functions["domain_objects"]["AutoScalingConfig"]
        MetricConfig = models_functions["domain_objects"]["MetricConfig"]
        LoadBalancerConfig = models_functions["domain_objects"]["LoadBalancerConfig"]
        LoadBalancerHealthCheckConfig = models_functions["domain_objects"]["LoadBalancerHealthCheckConfig"]
        InferenceContainer = models_functions["domain_objects"]["InferenceContainer"]
        
        # Create handler instance
        handler = CreateModelHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=dynamodb_table,
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


class TestDeleteModelHandler:
    """Test class for DeleteModelHandler."""
    
    def test_delete_model_handler(self, models_functions, mock_stepfunctions_client, 
                                 dynamodb_table, sample_model, mock_autoscaling_client):
        """Test DeleteModelHandler.__call__ method."""
        DeleteModelHandler = models_functions["handlers"]["DeleteModelHandler"]
        LISAModel = models_functions["domain_objects"]["LISAModel"]
        ModelNotFoundError = models_functions["exceptions"]["ModelNotFoundError"]
        
        # Add sample model to table
        dynamodb_table.put_item(Item=sample_model)

        # Create handler instance
        handler = DeleteModelHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=dynamodb_table,
        )

        # Call handler
        response = handler("test-model")

        # Verify response
        assert isinstance(response.model, LISAModel)
        assert response.model.modelId == "test-model"

        # Test with non-existent model
        with pytest.raises(ModelNotFoundError, match="Model 'non-existent-model' was not found"):
            handler("non-existent-model")


class TestGetModelHandler:
    """Test class for GetModelHandler."""
    
    def test_get_model_handler(self, models_functions, dynamodb_table, sample_model, 
                              mock_autoscaling_client, mock_stepfunctions_client):
        """Test GetModelHandler.__call__ method."""
        GetModelHandler = models_functions["handlers"]["GetModelHandler"]
        LISAModel = models_functions["domain_objects"]["LISAModel"]
        ModelNotFoundError = models_functions["exceptions"]["ModelNotFoundError"]
        
        # Add sample model to table
        dynamodb_table.put_item(Item=sample_model)

        # Create handler instance
        handler = GetModelHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=dynamodb_table,
        )

        # Call handler
        response = handler("test-model")

        # Verify response
        assert isinstance(response.model, LISAModel)
        assert response.model.modelId == "test-model"

        # Test with non-existent model
        with pytest.raises(ModelNotFoundError, match="Model 'non-existent-model' was not found"):
            handler("non-existent-model")


class TestListModelsHandler:
    """Test class for ListModelsHandler."""
    
    def test_list_models_handler(self, models_functions, dynamodb_table, sample_model, 
                                mock_autoscaling_client, mock_stepfunctions_client):
        """Test ListModelsHandler.__call__ method."""
        ListModelsHandler = models_functions["handlers"]["ListModelsHandler"]
        
        # Add sample model to table
        dynamodb_table.put_item(Item=sample_model)

        # Create another model
        another_model = sample_model.copy()
        another_model["model_id"] = "another-model"
        another_model["model_config"]["modelId"] = "another-model"
        dynamodb_table.put_item(Item=another_model)

        # Create handler instance
        handler = ListModelsHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=dynamodb_table,
        )

        # Call handler
        response = handler()

        # Verify response
        assert len(response.models) == 2
        model_ids = [model.modelId for model in response.models]
        assert "test-model" in model_ids
        assert "another-model" in model_ids


class TestUpdateModelHandler:
    """Test class for UpdateModelHandler."""
    
    def test_update_model_handler(self, models_functions, dynamodb_table, mock_autoscaling_client, 
                                 mock_stepfunctions_client, sample_model):
        """Test UpdateModelHandler.__call__ method."""
        UpdateModelHandler = models_functions["handlers"]["UpdateModelHandler"]
        UpdateModelRequest = models_functions["domain_objects"]["UpdateModelRequest"]
        LISAModel = models_functions["domain_objects"]["LISAModel"]
        ModelType = models_functions["domain_objects"]["ModelType"]
        ModelStatus = models_functions["domain_objects"]["ModelStatus"]
        ModelNotFoundError = models_functions["exceptions"]["ModelNotFoundError"]
        
        # Add sample model to table
        dynamodb_table.put_item(Item=sample_model)

        # Create model with STOPPED status for testing
        stopped_model = sample_model.copy()
        stopped_model["model_id"] = "stopped-model"
        stopped_model["model_config"]["modelId"] = "stopped-model"
        stopped_model["model_status"] = ModelStatus.STOPPED
        dynamodb_table.put_item(Item=stopped_model)

        # Create handler instance
        handler = UpdateModelHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=dynamodb_table,
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

    def test_update_model_validation(self, models_functions, dynamodb_table, mock_autoscaling_client, 
                                    mock_stepfunctions_client, sample_model):
        """Test validation in UpdateModelHandler."""
        UpdateModelHandler = models_functions["handlers"]["UpdateModelHandler"]
        UpdateModelRequest = models_functions["domain_objects"]["UpdateModelRequest"]
        AutoScalingInstanceConfig = models_functions["domain_objects"]["AutoScalingInstanceConfig"]
        ModelStatus = models_functions["domain_objects"]["ModelStatus"]
        InvalidStateTransitionError = models_functions["exceptions"]["InvalidStateTransitionError"]
        
        # Add sample model to table
        dynamodb_table.put_item(Item=sample_model)

        # Create model with STOPPED status for testing
        stopped_model = sample_model.copy()
        stopped_model["model_id"] = "stopped-model"
        stopped_model["model_config"]["modelId"] = "stopped-model"
        stopped_model["model_status"] = ModelStatus.STOPPED
        dynamodb_table.put_item(Item=stopped_model)

        # Create model with CREATING status for testing
        creating_model = sample_model.copy()
        creating_model["model_id"] = "creating-model"
        creating_model["model_config"]["modelId"] = "creating-model"
        creating_model["model_status"] = ModelStatus.CREATING
        dynamodb_table.put_item(Item=creating_model)

        # Create handler instance
        handler = UpdateModelHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=dynamodb_table,
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
        with pytest.raises(ValueError, match="Start or Stop operations and AutoScaling changes must happen in separate requests"):
            handler(
                "test-model",
                UpdateModelRequest(enabled=False, autoScalingInstanceConfig=AutoScalingInstanceConfig(minCapacity=1)),
            )

        # Test with non-LISA hosted model
        non_lisa_model = sample_model.copy()
        non_lisa_model["model_id"] = "non-lisa-model"
        non_lisa_model["model_config"]["modelId"] = "non-lisa-model"
        non_lisa_model.pop("auto_scaling_group", None)
        dynamodb_table.put_item(Item=non_lisa_model)

        with pytest.raises(ValueError, match="Cannot update AutoScaling Config for model not hosted in LISA infrastructure"):
            handler(
                "non-lisa-model", UpdateModelRequest(autoScalingInstanceConfig=AutoScalingInstanceConfig(minCapacity=1))
            )

        # Test with desiredCapacity > maxCapacity
        with pytest.raises(ValueError, match="Desired capacity cannot exceed ASG max"):
            handler(
                "test-model", UpdateModelRequest(autoScalingInstanceConfig=AutoScalingInstanceConfig(desiredCapacity=5))
            )


class TestExceptionHandlers:
    """Test class for exception handlers."""
    
    @pytest.mark.asyncio
    async def test_exception_handlers(self, models_functions):
        """Test exception handlers."""
        from fastapi.encoders import jsonable_encoder
        from fastapi.exceptions import RequestValidationError
        from models.lambda_functions import model_not_found_handler, user_error_handler, validation_exception_handler
        
        ModelNotFoundError = models_functions["exceptions"]["ModelNotFoundError"]
        ModelAlreadyExistsError = models_functions["exceptions"]["ModelAlreadyExistsError"]

        # Setup mock request
        request = MagicMock()

        # Test ModelNotFoundError handler
        exc = ModelNotFoundError("Model not found")
        response = await model_not_found_handler(request, exc)
        assert response.status_code == 404
        assert json.loads(response.body)["message"] == "Model not found"

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
        assert json.loads(response.body)["message"] == "Model already exists"

        # Test user error handler with ValueError
        exc = ValueError("Invalid value")
        response = await user_error_handler(request, exc)
        assert response.status_code == 400
        assert json.loads(response.body)["message"] == "Invalid value"


class TestFastAPIEndpoints:
    """Test class for FastAPI endpoints."""
    
    @pytest.mark.asyncio
    async def test_fastapi_endpoints(self, models_functions, sample_model, dynamodb_table, 
                                    mock_autoscaling_client, mock_stepfunctions_client):
        """Test FastAPI endpoints."""
        from fastapi.testclient import TestClient
        from models.lambda_functions import app
        
        CreateModelResponse = models_functions["domain_objects"]["CreateModelResponse"]
        LISAModel = models_functions["domain_objects"]["LISAModel"]
        ModelType = models_functions["domain_objects"]["ModelType"]
        ModelStatus = models_functions["domain_objects"]["ModelStatus"]

        # Create test client
        client = TestClient(app)

        # Setup mocks for the handlers
        with patch("models.lambda_functions.CreateModelHandler") as mock_create_handler, patch(
            "models.lambda_functions.ListModelsHandler"
        ) as mock_list_handler, patch("models.lambda_functions.GetModelHandler") as mock_get_handler, patch(
            "models.lambda_functions.UpdateModelHandler"
        ) as mock_update_handler, patch(
            "models.lambda_functions.DeleteModelHandler"
        ) as mock_delete_handler:

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

            # Test create model endpoint
            create_request = {
                "modelId": "new-model",
                "modelName": "new-model-name",
                "modelType": "textgen",
                "streaming": True,
            }
            response = client.post("/", json=create_request)
            assert response.status_code == 200
            data = response.json()
            assert data["model"]["modelId"] == "new-model"
            assert data["model"]["status"] == "Creating"

            # Test list models endpoint
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert len(data["models"]) == 1
            assert data["models"][0]["modelId"] == "existing-model"

            # Test get model endpoint
            response = client.get("/existing-model")
            assert response.status_code == 200
            data = response.json()
            assert data["model"]["modelId"] == "existing-model"

            # Test update model endpoint
            update_request = {"streaming": False}
            response = client.put("/existing-model", json=update_request)
            assert response.status_code == 200
            data = response.json()
            assert data["model"]["modelId"] == "existing-model"
            assert data["model"]["streaming"] is False

            # Test delete model endpoint
            response = client.delete("/existing-model")
            assert response.status_code == 200
            data = response.json()
            assert data["model"]["modelId"] == "existing-model"
            assert data["model"]["status"] == "Deleting"

    @pytest.mark.asyncio
    async def test_fastapi_model_not_found_endpoint(self):
        """Test FastAPI endpoint with model not found error."""
        from fastapi.testclient import TestClient
        from models.lambda_functions import app
        from models.exception import ModelNotFoundError

        client = TestClient(app)

        with patch("models.lambda_functions.GetModelHandler") as mock_get_handler:
            get_handler_instance = MagicMock()
            get_handler_instance.side_effect = ModelNotFoundError("Model 'non-existent' was not found")
            mock_get_handler.return_value = get_handler_instance

            response = client.get("/non-existent")
            assert response.status_code == 404
            data = response.json()
            assert data["message"] == "Model 'non-existent' was not found"

    @pytest.mark.asyncio
    async def test_fastapi_validation_error_endpoint(self):
        """Test FastAPI endpoint with validation error."""
        from fastapi.testclient import TestClient
        from models.lambda_functions import app

        client = TestClient(app)

        # Test create model with invalid request (missing required fields)
        invalid_request = {"modelName": "test-model"}  # Missing modelId, modelType
        response = client.post("/", json=invalid_request)
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert data["type"] == "RequestValidationError"

    @pytest.mark.asyncio
    async def test_fastapi_user_error_endpoint(self, models_functions):
        """Test FastAPI endpoint with user error."""
        from fastapi.testclient import TestClient
        from models.lambda_functions import app

        ModelAlreadyExistsError = models_functions["exceptions"]["ModelAlreadyExistsError"]
        client = TestClient(app)

        with patch("models.lambda_functions.CreateModelHandler") as mock_create_handler:
            create_handler_instance = MagicMock()
            create_handler_instance.side_effect = ModelAlreadyExistsError("Model 'existing-model' already exists")
            mock_create_handler.return_value = create_handler_instance

            create_request = {
                "modelId": "existing-model",
                "modelName": "existing-model-name",
                "modelType": "textgen",
                "streaming": True,
            }
            response = client.post("/", json=create_request)
            assert response.status_code == 400
            data = response.json()
            assert data["message"] == "Model 'existing-model' already exists"


class TestModelLambdaFunctions:
    """Test class for models lambda functions."""
    
    def test_lambda_handler(self, models_functions, lambda_context):
        """Test Lambda handler function."""
        from models.lambda_functions import handler
        
        # Test with FastAPI event
        fastapi_event = {
            "version": "2.0",
            "routeKey": "GET /models",
            "rawPath": "/models",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json",
                "content-length": "0",
                "host": "api.example.com",
                "user-agent": "test-client",
            },
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "abcdef123",
                "domainName": "api.example.com",
                "http": {
                    "method": "GET",
                    "path": "/models",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "192.0.2.1",
                },
                "requestId": "test-request-id",
                "stage": "prod",
                "time": "09/Apr/2015:12:34:56 +0000",
                "timeEpoch": 1428582896000,
            },
            "isBase64Encoded": False,
        }

        with patch("models.lambda_functions.ListModelsHandler") as mock_list_handler:
            list_handler_instance = MagicMock()
            list_models_response = {"models": []}
            list_handler_instance.return_value = list_models_response
            mock_list_handler.return_value = list_handler_instance

            response = handler(fastapi_event, lambda_context)
            
            assert response["statusCode"] == 200
            assert "body" in response
            assert "headers" in response

    def test_lambda_handler_with_exception(self, lambda_context):
        """Test Lambda handler with exception."""
        from models.lambda_functions import handler

        # Test with proper Lambda event that will cause an exception in the business logic
        event_with_exception = {
            "version": "2.0",
            "routeKey": "GET /non-existent-model",
            "rawPath": "/non-existent-model", 
            "rawQueryString": "",
            "headers": {
                "accept": "application/json",
                "content-length": "0",
                "host": "api.example.com",
                "user-agent": "test-client",
            },
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "abcdef123",
                "domainName": "api.example.com",
                "http": {
                    "method": "GET",
                    "path": "/non-existent-model",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "192.0.2.1",
                },
                "requestId": "test-request-id",
                "stage": "prod",
                "time": "09/Apr/2015:12:34:56 +0000",
                "timeEpoch": 1428582896000,
            },
            "isBase64Encoded": False,
        }

        # Mock GetModelHandler to raise an exception
        with patch("models.lambda_functions.GetModelHandler") as mock_get_handler:
            get_handler_instance = MagicMock()
            get_handler_instance.side_effect = Exception("Database connection failed")
            mock_get_handler.return_value = get_handler_instance

            response = handler(event_with_exception, lambda_context)

            # Should handle the exception gracefully
            assert response["statusCode"] == 500
            body = response["body"]
            # The response body might be plain text "Internal Server Error" or JSON
            if body.startswith("{"):
                parsed_body = json.loads(body)
                assert "error" in parsed_body or "message" in parsed_body
            else:
                # Plain text error response
                assert "error" in body.lower() or "internal server error" in body.lower()
