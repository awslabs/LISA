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

"""Base Handler definition for model management API definitions."""


from typing import Any, Union

from starlette.datastructures import Headers

from ..clients.litellm_client import LiteLLMClient


class BaseApiHandler:
    """Base Handler class for all model management APIs."""

    def __init__(self, base_uri: str, headers: Headers, verify: Union[str, bool]):
        """Create a LiteLLM client for all child objects to use."""
        self._litellm_client = LiteLLMClient(base_uri=base_uri, headers=headers, verify=verify)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """All handlers must implement the __call__ method."""
        raise NotImplementedError("__call__ method must be defined in child API Handler class.")
