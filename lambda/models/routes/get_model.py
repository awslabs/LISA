from typing import Annotated
from models.domain_objects.get_model_response import GetModelResponse
from fastapi import Path, APIRouter

router = APIRouter()

@router.get(path = '/{model_name}')
async def get_model(
    model_name: Annotated[str, Path(title="The name of the model to get")],
) -> GetModelResponse:
    return GetModelResponse(ModelName = model_name)