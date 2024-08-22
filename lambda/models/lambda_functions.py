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

from fastapi import FastAPI, Path
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware

from .domain_objects import (
    ContainerConfig,
    CreateModelRequest,
    CreateModelResponse,
    DeleteModelResponse,
    DescribeModelResponse,
    ListModelResponse,
    ModelStatus,
    ModelType,
    UpdateModelRequest,
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
async def create_model(model: CreateModelRequest) -> CreateModelResponse:
    """Endpoint to create a model."""
    # TODO add service to create model
    return CreateModelResponse(ModelId=model.ModelId, ModelName=model.ModelName, Status=ModelStatus.CREATING)


@app.get(path="", include_in_schema=False)  # type: ignore
@app.get(path="/")  # type: ignore
async def list_models() -> list[ListModelResponse]:
    """Endpoint to list models."""
    # TODO add service to list models
    return [
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


def _create_dummy_model(model_name: str, model_type: ModelType, model_status: ModelStatus) -> ListModelResponse:
    return ListModelResponse(
        ModelId=f"{model_name}_id",
        ModelName=model_name,
        ModelType=model_type,
        Status=model_status,
        Streaming=model_type == ModelType.TEXTGEN,
        ModelUrl="http://some.cool.alb.amazonaws.com/path/to/endpoint",
        ContainerConfig=ContainerConfig.DUMMY(),
    )


@app.get(path="/{model_id}")  # type: ignore
async def get_model(
    model_id: Annotated[str, Path(title="The name of the model to get")],
) -> DescribeModelResponse:
    """Endpoint to describe a model."""
    # TODO add service to get model
    return DescribeModelResponse.DUMMY(model_id, model_id)


@app.put(path="/{model_id}")  # type: ignore
async def put_model(
    model_id: Annotated[str, Path(title="The name of the model to update")], model: UpdateModelRequest
) -> DescribeModelResponse:
    """Endpoint to update a model."""
    # TODO add service to update model
    model.Status = ModelStatus.UPDATING
    return DescribeModelResponse(**model.model_dump())


@app.put(path="/{model_id}/start")  # type: ignore
async def start_model(model_id: Annotated[str, Path(title="The name of the model to start")]) -> ListModelResponse:
    """Endpoint to start a model."""
    # TODO add service to update model
    return ListModelResponse(
        ModelId=model_id,
        ModelName=model_id,
        ModelType=ModelType.TEXTGEN,
        Status=ModelStatus.CREATING,
        Streaming=True,
        ModelUrl="http://some.cool.alb.amazonaws.com/path/to/endpoint",
        ContainerConfig=ContainerConfig.DUMMY(),
    )


@app.put(path="/{model_id}/stop")  # type: ignore
async def stop_model(model_id: Annotated[str, Path(title="The name of the model to stop")]) -> ListModelResponse:
    """Endpoint to stop a model."""
    # TODO add service to update model
    return ListModelResponse(
        ModelId=model_id,
        ModelName=model_id,
        ModelType=ModelType.TEXTGEN,
        Status=ModelStatus.STOPPING,
        Streaming=True,
        ModelUrl="http://some.cool.alb.amazonaws.com/path/to/endpoint",
        ContainerConfig=ContainerConfig.DUMMY(),
    )


@app.delete(path="/{model_id}")  # type: ignore
async def delete_model(
    model_id: Annotated[str, Path(title="The name of the model to delete")],
) -> DeleteModelResponse:
    """Endpoint to delete a model."""
    # TODO add service to delete model
    return DeleteModelResponse(ModelId=model_id, ModelName=model_id)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/models")
docs = Mangum(app, lifespan="off")
