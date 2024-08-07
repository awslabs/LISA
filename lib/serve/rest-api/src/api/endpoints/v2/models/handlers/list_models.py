from ..domain_objects.get_model_response import GetModelResponse
from fastapi import APIRouter

router = APIRouter()

@router.get(path = '/')
async def list_models() -> list[GetModelResponse]:
    return [
        GetModelResponse(ModelName='my_first_model'),
        GetModelResponse(ModelName='my_second_model')
    ]