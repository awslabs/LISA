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
from typing import Annotated, Union

import boto3
import botocore.session
from fastapi import FastAPI, Path, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from utilities.common_functions import get_groups, is_admin, retry_config
from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware

from .domain_objects import (
    CreateModelRequest,
    CreateModelResponse,
    DeleteModelResponse,
    GetModelResponse,
    ListModelsResponse,
    UpdateModelRequest,
    UpdateModelResponse,
)
from .exception import InvalidStateTransitionError, ModelAlreadyExistsError, ModelNotFoundError
from .handler import CreateModelHandler, DeleteModelHandler, GetModelHandler, ListModelsHandler, UpdateModelHandler

sess = botocore.session.Session()
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

autoscaling = boto3.client("autoscaling", region_name=os.environ["AWS_REGION"], config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"])
stepfunctions = boto3.client("stepfunctions", region_name=os.environ["AWS_REGION"], config=retry_config)


@app.exception_handler(ModelNotFoundError)
async def model_not_found_handler(request: Request, exc: ModelNotFoundError) -> JSONResponse:
    """Handle exception when model cannot be found and translate to a 404 error."""
    return JSONResponse(status_code=404, content={"message": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle exception when request fails validation and and translate to a 422 error."""
    return JSONResponse(
        status_code=422, content={"detail": jsonable_encoder(exc.errors()), "type": "RequestValidationError"}
    )


@app.exception_handler(InvalidStateTransitionError)
@app.exception_handler(ModelAlreadyExistsError)
@app.exception_handler(ValueError)
async def user_error_handler(
    request: Request, exc: Union[InvalidStateTransitionError, ModelAlreadyExistsError, ValueError]
) -> JSONResponse:
    """Handle errors when customer requests options that cannot be processed."""
    return JSONResponse(status_code=400, content={"message": str(exc)})


@app.post(path="", include_in_schema=False)
@app.post(path="/")
async def create_model(create_request: CreateModelRequest) -> CreateModelResponse:
    """Endpoint to create a model."""
    create_handler = CreateModelHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
    )
    return create_handler(create_request=create_request)


@app.get(path="", include_in_schema=False)
@app.get(path="/")
async def list_models(request: Request) -> ListModelsResponse:
    """Endpoint to list models."""
    list_handler = ListModelsHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
    )

    user_groups = []
    admin_status = False

    if "aws.event" in request.scope:
        event = request.scope["aws.event"]
        try:
            user_groups = get_groups(event)
            admin_status = is_admin(event)
        except Exception:
            user_groups = []
            admin_status = False

    return list_handler(user_groups=user_groups, is_admin=admin_status)


@app.get(path="/{model_id}")
async def get_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to get")], request: Request
) -> GetModelResponse:
    """Endpoint to describe a model."""
    get_handler = GetModelHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
    )

    user_groups = []
    admin_status = False

    if "aws.event" in request.scope:
        event = request.scope["aws.event"]
        try:
            user_groups = get_groups(event)
            admin_status = is_admin(event)
        except Exception:
            user_groups = []
            admin_status = False

    return get_handler(model_id=model_id, user_groups=user_groups, is_admin=admin_status)


@app.put(path="/{model_id}")
async def update_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to update")],
    update_request: UpdateModelRequest,
) -> UpdateModelResponse:
    """Endpoint to update a model."""
    update_handler = UpdateModelHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
    )
    return update_handler(model_id=model_id, update_request=update_request)


@app.delete(path="/{model_id}")
async def delete_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to delete")], request: Request
) -> DeleteModelResponse:
    """Endpoint to delete a model."""
    delete_handler = DeleteModelHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
    )
    return delete_handler(model_id=model_id)


@app.get(path="/metadata/instances")
async def get_instances() -> list[str]:
    """Endpoint to list available instances in this region."""
    return list(sess.get_service_model("ec2").shape_for("InstanceType").enum)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/models")
docs = Mangum(app, lifespan="off")
