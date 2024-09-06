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

# Remove the following imports after APIs are no longer stubbed
from uuid import uuid4

import boto3
from fastapi import FastAPI, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from utilities.common_functions import retry_config
from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware

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

app = FastAPI(redirect_slashes=False, lifespan="off")
app.add_middleware(AWSAPIGatewayMiddleware)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)


def get_lisa_serve_endpoint() -> str:
    """Get LISA Serve base URI from SSM Parameter Store."""
    lisa_api_param_response = ssm_client.get_parameter(Name=os.environ["LISA_API_URL_PS_NAME"])
    lisa_api_endpoint = lisa_api_param_response["Parameter"]["Value"]
    return f"{lisa_api_endpoint}/{os.environ['REST_API_VERSION']}/serve"


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
    headers = request.headers
    create_handler = CreateModelHandler(
        base_uri=get_lisa_serve_endpoint(),
        headers=headers,
    )
    return create_handler(create_request=create_request)


@app.get(path="", include_in_schema=False)  # type: ignore
@app.get(path="/")  # type: ignore
async def list_models(request: Request) -> ListModelsResponse:
    """Endpoint to list models."""
    headers = request.headers
    list_handler = ListModelsHandler(
        base_uri=get_lisa_serve_endpoint(),
        headers=headers,
    )
    return list_handler()


def _create_dummy_model(model_name: str, model_type: ModelType, model_status: ModelStatus) -> LISAModel:
    return LISAModel(
        UniqueId=str(uuid4()),
        ModelId=f"{model_name}_id",
        ModelName=model_name,
        ModelType=model_type,
        Status=model_status,
        Streaming=model_type == ModelType.TEXTGEN,
        ModelUrl="http://some.cool.alb.amazonaws.com/path/to/endpoint",
        ContainerConfig=ContainerConfig(
            BaseImage=ContainerConfigImage(
                BaseImage="ghcr.io/huggingface/text-generation-inference:2.0.1",
                Path="lib/serve/ecs-model/textgen/tgi",
                Type="asset",
            ),
            SharedMemorySize=2048,
            HealthCheckConfig=ContainerHealthCheckConfig(
                Command=["CMD-SHELL", "exit 0"], Interval=10, StartPeriod=30, Timeout=5, Retries=5
            ),
            Environment={
                "MAX_CONCURRENT_REQUESTS": "128",
                "MAX_INPUT_LENGTH": "1024",
                "MAX_TOTAL_TOKENS": "2048",
            },
        ),
        AutoScalingConfig=AutoScalingConfig(
            MinCapacity=1,
            MaxCapacity=1,
            Cooldown=60,
            DefaultInstanceWarmup=60,
            MetricConfig=MetricConfig(
                AlbMetricName="RequestCountPerTarget",
                TargetValue=1000,
                Duration=60,
                EstimatedInstanceWarmup=30,
            ),
        ),
        LoadBalancerConfig=LoadBalancerConfig(
            HealthCheckConfig=LoadBalancerHealthCheckConfig(
                Path="/health",
                Interval=60,
                Timeout=30,
                HealthyThresholdCount=2,
                UnhealthyThresholdCount=10,
            ),
        ),
    )


@app.get(path="/{unique_id}")  # type: ignore
async def get_model(
    unique_id: Annotated[str, Path(title="The unique model ID of the model to get")], request: Request
) -> GetModelResponse:
    """Endpoint to describe a model."""
    headers = request.headers
    get_handler = GetModelHandler(
        base_uri=get_lisa_serve_endpoint(),
        headers=headers,
    )
    return get_handler(unique_id=unique_id)


@app.put(path="/{unique_id}")  # type: ignore
async def update_model(
    unique_id: Annotated[str, Path(title="The unique model ID of the model to update")],
    update_request: UpdateModelRequest,
) -> UpdateModelResponse:
    """Endpoint to update a model."""
    # TODO add service to update model
    model = _create_dummy_model("model_name", ModelType.TEXTGEN, ModelStatus.UPDATING)
    model.UniqueId = unique_id
    return UpdateModelResponse(model=unique_id)


@app.put(path="/{unique_id}/start")  # type: ignore
async def start_model(
    unique_id: Annotated[str, Path(title="The unique model ID of the model to start")]
) -> StartModelResponse:
    """Endpoint to start a model."""
    # TODO add service to update model
    model = _create_dummy_model("model_name", ModelType.TEXTGEN, ModelStatus.CREATING)
    model.UniqueId = unique_id
    return StartModelResponse(Model=model)


@app.put(path="/{unique_id}/stop")  # type: ignore
async def stop_model(
    unique_id: Annotated[str, Path(title="The unique model ID of the model to stop")]
) -> StopModelResponse:
    """Endpoint to stop a model."""
    # TODO add service to update model
    model = _create_dummy_model("model_name", ModelType.TEXTGEN, ModelStatus.STOPPING)
    model.UniqueId = unique_id
    return StopModelResponse(Model=model)


@app.delete(path="/{unique_id}")  # type: ignore
async def delete_model(
    unique_id: Annotated[str, Path(title="The unique model ID of the model to delete")], request: Request
) -> DeleteModelResponse:
    """Endpoint to delete a model."""
    headers = request.headers
    delete_handler = DeleteModelHandler(
        base_uri=get_lisa_serve_endpoint(),
        headers=headers,
    )
    return delete_handler(unique_id=unique_id)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/models")
docs = Mangum(app, lifespan="off")
