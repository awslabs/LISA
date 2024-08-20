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


@app.post(path="", include_in_schema=False)
@app.post(path="/")
async def create_model(model: CreateModelRequest) -> CreateModelResponse:
    """Endpoint to create a model."""
    # TODO add service to create model
    return CreateModelResponse(ModelId=model.ModelId, ModelName=model.ModelName, Status=ModelStatus.CREATING)


@app.get(path="", include_in_schema=False)
@app.get(path="/")
async def list_models() -> list[ListModelResponse]:
    """Endpoint to list models."""
    # TODO add service to list models
    return [
        ListModelResponse(
            ModelId="my_first_model",
            ModelName="my_first_model",
            ModelType=ModelType.TEXTGEN,
            Status=ModelStatus.CREATING,
            Streaming=True,
            ModelUrl="http://some.cool.alb.amazonaws.com/path/to/endpoint",
            ContainerConfig=ContainerConfig.DUMMY(),
        ),
        ListModelResponse(
            ModelId="my_second_model",
            ModelName="my_second_model",
            ModelType=ModelType.TEXTGEN,
            Status=ModelStatus.IN_SERVICE,
            Streaming=True,
            ModelUrl="http://some.cool.alb.amazonaws.com/path/to/endpoint",
            ContainerConfig=ContainerConfig.DUMMY(),
        ),
    ]


@app.get(path="/{model_id}")
async def get_model(
    model_id: Annotated[str, Path(title="The name of the model to get")],
) -> DescribeModelResponse:
    """Endpoint to describe a model."""
    # TODO add service to get model
    return DescribeModelResponse.DUMMY(model_id, model_id)


@app.put(path="/{model_id}")
async def put_model(
    model_id: Annotated[str, Path(title="The name of the model to update")], model: UpdateModelRequest
) -> DescribeModelResponse:
    """Endpoint to update a model."""
    # TODO add service to update model
    model.Status = ModelStatus.UPDATING
    return DescribeModelResponse(**model.model_dump())


@app.put(path="/{model_id}/start")
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


@app.put(path="/{model_id}/stop")
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


@app.delete(path="/{model_id}")
async def delete_model(
    model_id: Annotated[str, Path(title="The name of the model to delete")],
) -> DeleteModelResponse:
    """Endpoint to delete a model."""
    # TODO add service to delete model
    return DeleteModelResponse(ModelId=model_id, ModelName=model_id)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/models")
docs = Mangum(app, lifespan="off")
