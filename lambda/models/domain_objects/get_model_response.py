from pydantic import BaseModel

class GetModelResponse(BaseModel):
    ModelName: str