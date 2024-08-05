from pydantic import BaseModel

class DeleteModelResponse(BaseModel):
    ModelName: str
    Status: str = "DELETED"