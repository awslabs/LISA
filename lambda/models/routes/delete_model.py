from typing import Annotated
from models.domain_objects.delete_model import DeleteModelResponse
from fastapi import Path
from .. import router

@router.delete(path = '/{model_name}')
async def delete_model(
    model_name: Annotated[str, Path(title="The name of the model to delete")],
) -> DeleteModelResponse:
    return DeleteModelResponse(ModelName = model_name)