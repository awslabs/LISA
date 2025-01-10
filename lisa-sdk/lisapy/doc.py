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

from .common import BaseMixin
from .errors import parse_error


class DocsMixin(BaseMixin):
    """Mixin for doc-related operations."""

    def list_docs(self) -> str:
        response = self._session.get(f"{self.url}/docs")
        if response.status_code == 200:
            html: str = response.text
            return html
        else:
            raise parse_error(response.status_code, response)
