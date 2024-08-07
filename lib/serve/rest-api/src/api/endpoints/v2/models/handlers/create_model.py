from ..domain_objects.create_model import CreateModelRequest, CreateModelResponse, ModelCreateStatus
from fastapi import APIRouter

router = APIRouter()

@router.post(path = '/')
async def create_model(model: CreateModelRequest) -> CreateModelResponse:
    #TODO: put your business logic
    return CreateModelResponse(ModelName = model.ModelName, Status = ModelCreateStatus.CREATING)