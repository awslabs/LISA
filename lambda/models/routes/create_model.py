from models.domain_objects.create_model import CreateModelRequest, CreateModelResponse, ModelCreateStatus
from .. import router

@router.post(path = '/')
async def create_model(model: CreateModelRequest) -> CreateModelResponse:
    return CreateModelResponse(ModelName = model.ModelName, Status = ModelCreateStatus.CREATING)