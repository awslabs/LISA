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

"""Handler for DeleteModel requests."""

import json
import logging
import os

from models.exception import ModelInUseError, ModelNotFoundError
from repository.vector_store_repo import VectorStoreRepository

from ..domain_objects import DeleteModelResponse
from .base_handler import BaseApiHandler
from .utils import to_lisa_model

logger = logging.getLogger(__name__)


class DeleteModelHandler(BaseApiHandler):
    """Handler class for DeleteModel requests."""

    def __call__(self, model_id: str) -> DeleteModelResponse:  # type: ignore
        """Kick off state machine to delete infrastructure and remove model reference from LiteLLM."""
        table_item = self._model_table.get_item(Key={"model_id": model_id}).get("Item", None)
        if not table_item:
            raise ModelNotFoundError(f"Model '{model_id}' was not found")

        # Check if model is associated with any pipelines (embedding models only)
        self._check_model_in_use(model_id)

        self._stepfunctions.start_execution(
            stateMachineArn=os.environ["DELETE_SFN_ARN"], input=json.dumps({"modelId": model_id})
        )

        lisa_model = to_lisa_model(table_item)
        return DeleteModelResponse(model=lisa_model)

    def _check_model_in_use(self, model_id: str) -> None:
        """Check if model is in use by any repository or pipeline.

        Args:
            model_id: The model ID to check

        Raises:
            InvalidStateTransitionError: If model is in use by any repository or pipeline
        """
        vector_store_repo = VectorStoreRepository()
        usages = vector_store_repo.find_repositories_using_model(model_id)

        if usages:
            usage = usages[0]  # Report the first usage found
            repository_id = usage["repository_id"]
            usage_type = usage["usage_type"]

            logger.warning(
                f"Model '{model_id}' is in use by repository '{repository_id}' (resource: {usage_type}). "
                "Cannot delete."
            )
            raise ModelInUseError(
                f"Model '{model_id}' is currently in use by repository '{repository_id}' (resource: {usage_type}). "
                "Please remove the model from the repository before deleting."
            )
