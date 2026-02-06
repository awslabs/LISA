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


"""Exceptions from handling RAG documents."""


class RagUploadException(Exception):
    """RAG upload error exception."""


class HTTPException(Exception):
    def __init__(self, status_code: int = 400, message: str = "Bad Request") -> None:
        super().__init__(status_code, message)
        self.http_status_code = status_code
        self.message = message


class NotFoundException(HTTPException):
    def __init__(self, detail: str = "Not Found"):
        super().__init__(404, detail)  # flake8: noqa


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(401, detail)  # flake8: noqa


class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(403, detail)  # flake8: noqa
