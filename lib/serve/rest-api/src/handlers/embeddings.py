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

"""Embedding route handlers."""
import logging
from typing import Any, Dict

from ..utils.request_utils import validate_and_prepare_llm_request
from ..utils.resources import RestApiResource

logger = logging.getLogger(__name__)


async def handle_embeddings(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle for embeddings endpoint."""
    model, model_kwargs, text = await validate_and_prepare_llm_request(request_data, RestApiResource.EMBEDDINGS)
    response = await model.embed_query(text=text, model_kwargs=model_kwargs)

    return response.dict()  # type: ignore
