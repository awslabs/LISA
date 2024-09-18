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

"""Exception definitions for model management APIs."""


# LiteLLM errors


class ModelNotFoundError(LookupError):
    """Error to raise when a specified model cannot be found in the database."""

    pass


class ModelAlreadyExistsError(LookupError):
    """Error to raise when a specified model already exists in the database."""

    pass


# State machine exceptions


class MaxPollsExceededException(Exception):
    """Exception to indicate that polling for a state timed out."""

    pass


class StackFailedToCreateException(Exception):
    """Exception to indicate that the CDK for creating a model stack failed."""

    pass


class UnexpectedCloudFormationStateException(Exception):
    """Exception to indicate that the CloudFormation stack has transitioned to a non-healthy state."""

    pass
