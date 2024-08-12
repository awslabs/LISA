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
from typing import Annotated
from fastapi import Path, APIRouter, status
from models.domain_objects import GetModelResponse

router = APIRouter()

@router.get(path = '/{model_name}', status_code = status. HTTP_200_OK)
async def get_model(
    model_name: Annotated[str, Path(title="The name of the model to get")],
) -> GetModelResponse:
    # TODO add service to get model
    return GetModelResponse(ModelName = model_name)