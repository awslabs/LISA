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


class TokenAlreadyExistsError(LookupError):
    """Error to raise when a user token already exists in the database."""

    pass


class TokenNotFoundError(Exception):
    """Raised when a token cannot be found."""

    pass


class UnauthorizedError(Exception):
    """Raised when user is not authorized to perform an action"""

    pass


class ForbiddenError(Exception):
    """Raised when user lacks required permissions"""

    pass
