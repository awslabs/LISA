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

"""Common utility functions across all API handlers."""

from typing import Any, Dict

from ..domain_objects import LISAModel


def to_lisa_model(model_dict: Dict[str, Any]) -> LISAModel:
    """Convert DDB model entry dictionary to a LISAModel object."""
    model_dict["model_config"]["status"] = model_dict["model_status"]
    if "model_url" in model_dict:
        model_dict["model_config"]["modelUrl"] = model_dict["model_url"]
    lisa_model: LISAModel = LISAModel.model_validate(model_dict["model_config"])
    return lisa_model
