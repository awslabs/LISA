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
from typing import Annotated

# Remove the following imports after APIs are no longer stubbed
from uuid import uuid4

from fastapi import FastAPI, Path
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
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


@app.post(path="", include_in_schema=False)  # type: ignore
@app.post(path="/")  # type: ignore
async def create_model(create_request: CreateModelRequest) -> CreateModelResponse:
    """Endpoint to create a model."""
    # TODO add service to create model
    return CreateModelResponse(
        Model=_create_dummy_model(create_request.ModelName, ModelType.TEXTGEN, ModelStatus.CREATING)
    )


@app.get(path="", include_in_schema=False)  # type: ignore
@app.get(path="/")  # type: ignore
async def list_models() -> ListModelsResponse:
    """Endpoint to list models."""
    return ListModelsResponse(
        Models=[
            _create_dummy_model("my_first_model", ModelType.TEXTGEN, ModelStatus.CREATING),
            _create_dummy_model("my_second_model", ModelType.EMBEDDING, ModelStatus.IN_SERVICE),
            _create_dummy_model("my_third_model", ModelType.EMBEDDING, ModelStatus.STOPPING),
            _create_dummy_model("my_fourth_model", ModelType.TEXTGEN, ModelStatus.STOPPED),
            _create_dummy_model("my_fifth_model", ModelType.EMBEDDING, ModelStatus.UPDATING),
            _create_dummy_model("my_sixth_model", ModelType.EMBEDDING, ModelStatus.DELETING),
            _create_dummy_model("my_seventh_model", ModelType.TEXTGEN, ModelStatus.FAILED),
            _create_dummy_model("my_eighth_model", ModelType.TEXTGEN, ModelStatus.FAILED),
            _create_dummy_model("my_ninth_model", ModelType.EMBEDDING, ModelStatus.DELETING),
            _create_dummy_model("my_tenth_model", ModelType.TEXTGEN, ModelStatus.UPDATING),
            _create_dummy_model("my_eleventh_model", ModelType.EMBEDDING, ModelStatus.STOPPED),
            _create_dummy_model("my_twelfth_model", ModelType.EMBEDDING, ModelStatus.STOPPING),
            _create_dummy_model("my_thirteenth_model", ModelType.TEXTGEN, ModelStatus.IN_SERVICE),
            _create_dummy_model("my_fourteenth_model", ModelType.TEXTGEN, ModelStatus.CREATING),
            _create_dummy_model("my_fifteenth_model", ModelType.EMBEDDING, ModelStatus.CREATING),
            _create_dummy_model("my_sixteenth_model", ModelType.TEXTGEN, ModelStatus.IN_SERVICE),
            _create_dummy_model("my_seventeenth_model", ModelType.EMBEDDING, ModelStatus.STOPPING),
            _create_dummy_model("my_eighteenth_model", ModelType.EMBEDDING, ModelStatus.STOPPED),
            _create_dummy_model("my_nineteenth_model", ModelType.EMBEDDING, ModelStatus.UPDATING),
            _create_dummy_model("my_twentieth_model", ModelType.TEXTGEN, ModelStatus.DELETING),
            _create_dummy_model("my_twenty_first_model", ModelType.TEXTGEN, ModelStatus.FAILED),
            _create_dummy_model("my_twenty_second_model", ModelType.EMBEDDING, ModelStatus.FAILED),
            _create_dummy_model("my_twenty_third_model", ModelType.EMBEDDING, ModelStatus.DELETING),
            _create_dummy_model("my_twenty_fourth_model", ModelType.TEXTGEN, ModelStatus.UPDATING),
            _create_dummy_model("my_twenty_fifth_model", ModelType.TEXTGEN, ModelStatus.STOPPED),
            _create_dummy_model("my_twenty_sixth_model", ModelType.TEXTGEN, ModelStatus.IN_SERVICE),
        ]
    )


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
    unique_id: Annotated[str, Path(title="The unique model ID of the model to get")],
) -> GetModelResponse:
    """Endpoint to describe a model."""
    # TODO add service to get model
    model = _create_dummy_model("model_name", ModelType.TEXTGEN, ModelStatus.IN_SERVICE)
    model.UniqueId = unique_id
    return GetModelResponse(Model=model)


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


@app.delete(path="/{model_id}")  # type: ignore
async def delete_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to delete")],
) -> DeleteModelResponse:
    """Endpoint to delete a model."""
    # TODO add service to delete model
    return DeleteModelResponse(ModelId=model_id, ModelName=model_id)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/models")
docs = Mangum(app, lifespan="off")
