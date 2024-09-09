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

"""APIGW endpoints for managing models."""
import os
from typing import Annotated

import boto3
from fastapi import FastAPI, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config
from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware

from .clients.litellm_client import LiteLLMClient
from .domain_objects import (
    AutoScalingConfig,
    ContainerConfig,
    ContainerConfigImage,
    ContainerHealthCheckConfig,
    CreateModelRequest,
    CreateModelResponse,
    DeleteModelResponse,
    GetModelResponse,
    LISAModel,
    ListModelsResponse,
    LoadBalancerConfig,
    LoadBalancerHealthCheckConfig,
    MetricConfig,
    ModelStatus,
    ModelType,
    StartModelResponse,
    StopModelResponse,
    UpdateModelRequest,
    UpdateModelResponse,
)
from .exception import ModelAlreadyExistsError, ModelNotFoundError
from .handler import CreateModelHandler, DeleteModelHandler, GetModelHandler, ListModelsHandler

app = FastAPI(redirect_slashes=False, lifespan="off", docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(AWSAPIGatewayMiddleware)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

stepfunctions = boto3.client("stepfunctions", region_name=os.environ["AWS_REGION"], config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"])
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)


@app.exception_handler(ModelNotFoundError)  # type: ignore
async def model_not_found_handler(request: Request, exc: ModelNotFoundError) -> JSONResponse:
    """Handle exception when model cannot be found and translate to a 404 error."""
    return JSONResponse(status_code=404, content={"message": str(exc)})


@app.exception_handler(ModelAlreadyExistsError)  # type: ignore
async def model_already_exists_handler(request: Request, exc: ModelAlreadyExistsError) -> JSONResponse:
    """Handle exception when model is found and translate to a 400 error."""
    return JSONResponse(status_code=400, content={"message": str(exc)})


@app.post(path="", include_in_schema=False)  # type: ignore
@app.post(path="/")  # type: ignore
async def create_model(create_request: CreateModelRequest, request: Request) -> CreateModelResponse:
    """Endpoint to create a model."""
    create_handler = CreateModelHandler(
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        litellm_client=LiteLLMClient(
            base_uri=get_rest_api_container_endpoint(), headers=request.headers, verify=get_cert_path(iam_client)
        ),
    )
    return create_handler(create_request=create_request)


@app.get(path="", include_in_schema=False)  # type: ignore
@app.get(path="/")  # type: ignore
async def list_models(request: Request) -> ListModelsResponse:
    """Endpoint to list models."""
    list_handler = ListModelsHandler(
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        litellm_client=LiteLLMClient(
            base_uri=get_rest_api_container_endpoint(), headers=request.headers, verify=get_cert_path(iam_client)
        ),
    )
    return list_handler()


def _create_dummy_model(model_name: str, model_type: ModelType, model_status: ModelStatus) -> LISAModel:
    return LISAModel(
        modelId=f"{model_name}_id",
        modelName=model_name,
        modelType=model_type,
        status=model_status,
        streaming=model_type == ModelType.TEXTGEN,
        modelUrl="http://some.cool.alb.amazonaws.com/path/to/endpoint",
        containerConfig=ContainerConfig(
            baseImage=ContainerConfigImage(
                baseImage="ghcr.io/huggingface/text-generation-inference:2.0.1",
                path="lib/serve/ecs-model/textgen/tgi",
                type="asset",
            ),
            sharedMemorySize=2048,
            healthCheckConfig=ContainerHealthCheckConfig(
                command=["CMD-SHELL", "exit 0"], Interval=10, StartPeriod=30, Timeout=5, Retries=5
            ),
            environment={
                "MAX_CONCURRENT_REQUESTS": "128",
                "MAX_INPUT_LENGTH": "1024",
                "MAX_TOTAL_TOKENS": "2048",
            },
        ),
        autoScalingConfig=AutoScalingConfig(
            minCapacity=1,
            maxCapacity=1,
            cooldown=60,
            defaultInstanceWarmup=60,
            metricConfig=MetricConfig(
                albMetricName="RequestCountPerTarget",
                targetValue=1000,
                duration=60,
                estimatedInstanceWarmup=30,
            ),
        ),
        loadBalancerConfig=LoadBalancerConfig(
            healthCheckConfig=LoadBalancerHealthCheckConfig(
                path="/health",
                interval=60,
                timeout=30,
                healthyThresholdCount=2,
                unhealthyThresholdCount=10,
            ),
        ),
    )


@app.get(path="/{model_id}")  # type: ignore
async def get_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to get")], request: Request
) -> GetModelResponse:
    """Endpoint to describe a model."""
    get_handler = GetModelHandler(
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        litellm_client=LiteLLMClient(
            base_uri=get_rest_api_container_endpoint(), headers=request.headers, verify=get_cert_path(iam_client)
        ),
    )
    return get_handler(model_id=model_id)


@app.put(path="/{model_id}")  # type: ignore
async def update_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to update")],
    update_request: UpdateModelRequest,
) -> UpdateModelResponse:
    """Endpoint to update a model."""
    # TODO add service to update model
    model = _create_dummy_model("model_name", ModelType.TEXTGEN, ModelStatus.UPDATING)
    return UpdateModelResponse(model=model)


@app.put(path="/{model_id}/start")  # type: ignore
async def start_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to start")]
) -> StartModelResponse:
    """Endpoint to start a model."""
    # TODO add service to update model
    model = _create_dummy_model("model_name", ModelType.TEXTGEN, ModelStatus.CREATING)
    return StartModelResponse(model=model)


@app.put(path="/{model_id}/stop")  # type: ignore
async def stop_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to stop")]
) -> StopModelResponse:
    """Endpoint to stop a model."""
    # TODO add service to update model
    model = _create_dummy_model("model_name", ModelType.TEXTGEN, ModelStatus.STOPPING)
    return StopModelResponse(model=model)


@app.delete(path="/{model_id}")  # type: ignore
async def delete_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to delete")], request: Request
) -> DeleteModelResponse:
    """Endpoint to delete a model."""
    delete_handler = DeleteModelHandler(
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        litellm_client=LiteLLMClient(
            base_uri=get_rest_api_container_endpoint(), headers=request.headers, verify=get_cert_path(iam_client)
        ),
    )
    return delete_handler(model_id=model_id)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/models")
docs = Mangum(app, lifespan="off")
