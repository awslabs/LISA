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
import logging
import os
from typing import Annotated, Union
from urllib.parse import urlparse

import boto3
import botocore.session
from fastapi import HTTPException, Path, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from utilities.auth import get_groups, get_username, is_admin
from utilities.common_functions import retry_config
from utilities.fastapi_factory import create_fastapi_app

from .domain_objects import (
    CreateModelRequest,
    CreateModelResponse,
    DeleteModelResponse,
    DeleteScheduleResponse,
    GetModelResponse,
    GetScheduleResponse,
    GetScheduleStatusResponse,
    ListModelsResponse,
    SchedulingConfig,
    UpdateModelRequest,
    UpdateModelResponse,
    UpdateScheduleResponse,
)
from .exception import InvalidStateTransitionError, ModelAlreadyExistsError, ModelInUseError, ModelNotFoundError
from .handler import (
    CreateModelHandler,
    DeleteModelHandler,
    DeleteScheduleHandler,
    GetModelHandler,
    GetScheduleHandler,
    GetScheduleStatusHandler,
    ListModelsHandler,
    UpdateModelHandler,
    UpdateScheduleHandler,
)

logger = logging.getLogger(__name__)

sess = botocore.session.Session()
app = create_fastapi_app()

autoscaling = boto3.client("autoscaling", region_name=os.environ["AWS_REGION"], config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"])
guardrails_table = dynamodb.Table(os.environ["GUARDRAILS_TABLE_NAME"])
stepfunctions = boto3.client("stepfunctions", region_name=os.environ["AWS_REGION"], config=retry_config)


def get_admin_status_and_groups(request: Request) -> tuple[bool, list[str]]:
    admin_status = False
    user_groups = []

    if "aws.event" in request.scope:
        event = request.scope["aws.event"]
        try:
            user_groups = get_groups(event)
            admin_status = is_admin(event)
        except Exception:
            user_groups = []
            admin_status = False
    return admin_status, user_groups


@app.exception_handler(ModelNotFoundError)
async def model_not_found_handler(request: Request, exc: ModelNotFoundError) -> JSONResponse:
    """Handle exception when model cannot be found and translate to a 404 error."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidStateTransitionError)
@app.exception_handler(ModelAlreadyExistsError)
@app.exception_handler(ValueError)
async def user_error_handler(
    request: Request, exc: Union[InvalidStateTransitionError, ModelAlreadyExistsError, ValueError]
) -> JSONResponse:
    """Handle errors when customer requests options that cannot be processed."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ModelInUseError)
async def model_in_use_handler(request: Request, exc: ModelInUseError) -> JSONResponse:
    """Handle exception when attempting to delete a model that is in use."""
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.post(path="", include_in_schema=False)
@app.post(path="/")
async def create_model(create_request: CreateModelRequest, request: Request) -> CreateModelResponse:
    """Endpoint to create a model."""
    admin_status, user_groups = get_admin_status_and_groups(request)
    if not admin_status:
        raise HTTPException(status_code=403, detail="User does not have permission to create models.")

    # Extract user context for audit logging
    event = request.scope.get("aws.event", {})
    username = get_username(event) if event else "unknown"
    auth_type = event.get("requestContext", {}).get("authorizer", {}).get("authType", "unknown")
    source_ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp", "unknown")

    # Extract container image and healthcheck details for audit logging
    container_image = None
    registry_domain = None
    healthcheck_command = None

    if create_request.containerConfig:
        container_image = create_request.containerConfig.image.baseImage
        # Extract registry domain from image URL
        try:
            if "://" in container_image:
                registry_domain = urlparse(container_image).netloc
            elif "/" in container_image:
                registry_domain = container_image.split("/")[0]
            else:
                registry_domain = "unknown"
        except Exception:
            registry_domain = "parse_error"

        healthcheck_command = create_request.containerConfig.healthCheckConfig.command

    # Log CreateModel request for security audit
    logger.info(
        "CreateModel request",
        extra={
            "event_type": "CREATE_MODEL_REQUEST",
            "user": {
                "username": username,
                "groups": user_groups,
                "auth_type": auth_type,
                "source_ip": source_ip,
            },
            "model": {
                "model_id": create_request.modelId,
                "model_name": create_request.modelName,
                "instance_type": create_request.instanceType if hasattr(create_request, "instanceType") else None,
                "auto_scaling": (
                    {
                        "min_capacity": (
                            create_request.autoScalingConfig.minCapacity if create_request.autoScalingConfig else None
                        ),
                        "max_capacity": (
                            create_request.autoScalingConfig.maxCapacity if create_request.autoScalingConfig else None
                        ),
                    }
                    if create_request.autoScalingConfig
                    else None
                ),
            },
            "container": (
                {
                    "base_image": container_image,
                    "registry_domain": registry_domain,
                    "image_type": create_request.containerConfig.image.type if create_request.containerConfig else None,
                    "healthcheck_command": healthcheck_command,
                }
                if create_request.containerConfig
                else None
            ),
        },
    )

    create_handler = CreateModelHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )
    try:
        response = create_handler(create_request=create_request)

        # Log successful creation
        logger.info(
            "CreateModel request successful",
            extra={
                "event_type": "CREATE_MODEL_SUCCESS",
                "model_id": create_request.modelId,
                "username": username,
            },
        )

        return response
    except ModelAlreadyExistsError as e:
        # Log failure
        logger.warning(
            "CreateModel request failed - model already exists",
            extra={
                "event_type": "CREATE_MODEL_FAILURE",
                "model_id": create_request.modelId,
                "username": username,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        # Log unexpected failure
        logger.error(
            "CreateModel request failed with unexpected error",
            extra={
                "event_type": "CREATE_MODEL_ERROR",
                "model_id": create_request.modelId,
                "username": username,
                "error": str(e),
            },
            exc_info=True,
        )
        raise


@app.get(path="", include_in_schema=False)
@app.get(path="/")
async def list_models(request: Request) -> ListModelsResponse:
    """Endpoint to list models."""
    list_handler = ListModelsHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )

    admin_status, user_groups = get_admin_status_and_groups(request)
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
        guardrails_table_resource=guardrails_table,
    )

    admin_status, user_groups = get_admin_status_and_groups(request)
    try:
        return get_handler(model_id=model_id, user_groups=user_groups, is_admin=admin_status)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.put(path="/{model_id}")
async def update_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to update")],
    update_request: UpdateModelRequest,
    request: Request,
) -> UpdateModelResponse:
    """Endpoint to update a model."""
    admin_status, _ = get_admin_status_and_groups(request)
    if not admin_status:
        raise HTTPException(status_code=403, detail="User does not have permission to update models")
    update_handler = UpdateModelHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )
    try:
        return update_handler(model_id=model_id, update_request=update_request)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete(path="/{model_id}")
async def delete_model(
    model_id: Annotated[str, Path(title="The unique model ID of the model to delete")], request: Request
) -> DeleteModelResponse:
    """Endpoint to delete a model."""
    admin_status, _ = get_admin_status_and_groups(request)
    if not admin_status:
        raise HTTPException(status_code=403, detail="User does not have permission to delete models")
    delete_handler = DeleteModelHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
    )
    try:
        return delete_handler(model_id=model_id)
    except ModelInUseError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get(path="/metadata/instances")
async def get_instances() -> list[str]:
    """Endpoint to list available instances in this region."""
    return list(sess.get_service_model("ec2").shape_for("InstanceType").enum)


@app.post(path="/{model_id}/schedule")
@app.put(path="/{model_id}/schedule")
async def update_schedule(
    model_id: Annotated[str, Path(title="The unique model ID of the model to schedule")],
    schedule_config: SchedulingConfig,
    request: Request,
) -> UpdateScheduleResponse:
    """Endpoint to create or update a schedule for a model"""
    update_schedule_handler = UpdateScheduleHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
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

    return update_schedule_handler(
        model_id=model_id, schedule_config=schedule_config, user_groups=user_groups, is_admin=admin_status
    )


@app.get(path="/{model_id}/schedule")
async def get_schedule(
    model_id: Annotated[str, Path(title="The unique model ID of the model to get schedule for")], request: Request
) -> GetScheduleResponse:
    """Endpoint to get current schedule configuration for a model"""
    get_schedule_handler = GetScheduleHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
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

    return get_schedule_handler(model_id=model_id, user_groups=user_groups, is_admin=admin_status)


@app.delete(path="/{model_id}/schedule")
async def delete_schedule(
    model_id: Annotated[str, Path(title="The unique model ID of the model to delete schedule for")], request: Request
) -> DeleteScheduleResponse:
    """Endpoint to delete a schedule for a model"""
    delete_schedule_handler = DeleteScheduleHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
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

    return delete_schedule_handler(model_id=model_id, user_groups=user_groups, is_admin=admin_status)


@app.get(path="/{model_id}/schedule/status")
async def get_schedule_status(
    model_id: Annotated[str, Path(title="The unique model ID of the model to get schedule status for")],
    request: Request,
) -> GetScheduleStatusResponse:
    """Endpoint to get current schedule status and next scheduled action for a model"""
    get_schedule_status_handler = GetScheduleStatusHandler(
        autoscaling_client=autoscaling,
        stepfunctions_client=stepfunctions,
        model_table_resource=model_table,
        guardrails_table_resource=guardrails_table,
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

    return get_schedule_status_handler(model_id=model_id, user_groups=user_groups, is_admin=admin_status)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/models")
docs = Mangum(app, lifespan="off")
