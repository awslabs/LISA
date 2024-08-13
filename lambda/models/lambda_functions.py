from fastapi import FastAPI, Path, status, Request
from mangum import Mangum
from typing import Annotated
from models.domain_objects import GetModelResponse, CreateModelRequest, CreateModelResponse, ModelStatus, DeleteModelResponse

app = FastAPI(redirect_slashes=False, lifespan="off")

@app.middleware("http")
async def set_root_path_for_api_gateway(request: Request, call_next):    
    """Sets the FastAPI root_path dynamically from the ASGI request data."""

    print(f"request.scope : {request.scope['root_path']}")

    root_path = request.scope["root_path"]
    print(f"root_path : {root_path}")
    
    if root_path:
        app.root_path = root_path
    else:
        # fetch from AWS requestContext
        if "aws.event" in request.scope:
            context = request.scope["aws.event"]["requestContext"]

            if "pathParameters" in request.scope["aws.event"]:
                if request.scope['aws.event']['pathParameters'] is not None and 'proxy' in request.scope['aws.event']['pathParameters']:
                    request.scope["path"] = f"/{request.scope['aws.event']['pathParameters']['proxy']}"
                    path_parameters = request.scope["aws.event"]["pathParameters"]
                    root_path = context['path'] [ : context['path'].find(path_parameters["proxy"]) ]
                    request.scope["root_path"] = root_path

    response = await call_next(request)
    return response


@app.post(path = '', status_code = status.HTTP_200_OK, include_in_schema=False)
@app.post(path = '/', status_code = status.HTTP_200_OK)
async def create_model(model: CreateModelRequest) -> CreateModelResponse:
    # TODO add service to create model
    return CreateModelResponse(ModelName = model.ModelName, Status = ModelStatus.CREATING);


@app.get(path = '', status_code = status. HTTP_200_OK, include_in_schema=False)
@app.get(path = '/', status_code = status. HTTP_200_OK)
async def list_models() -> list[GetModelResponse]:
    # TODO add service to list models
    return [
        GetModelResponse(ModelName='my_first_model'),
        GetModelResponse(ModelName='my_second_model')
    ]


@app.get(path = '/{model_name}', status_code = status. HTTP_200_OK)
async def get_model(
    model_name: Annotated[str, Path(title="The name of the model to get")],
) -> GetModelResponse:
    # TODO add service to get model
    return GetModelResponse(ModelName = model_name)


@app.delete(path = '/{model_name}', status_code = status. HTTP_200_OK)
async def delete_model(
    model_name: Annotated[str, Path(title="The name of the model to delete")],
) -> DeleteModelResponse:
    # TODO add service to delete model
    return DeleteModelResponse(ModelName = model_name)


handler = Mangum(app, lifespan="off", api_gateway_base_path='/models')