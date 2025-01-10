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

from typing import Dict, List

from .common import BaseMixin
from .errors import parse_error


class ConfigMixin(BaseMixin):
    """Mixin for config-related operations."""

    def get_configs(self) -> List[Dict]:
        response = self._session.get(f"{self.url}/configuration")
        if response.status_code == 200:
            json_configs: List[Dict] = response.json()
            return json_configs
        else:
            raise parse_error(response.status_code, response)
