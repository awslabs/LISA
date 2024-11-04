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

"""Module to create and set environment variables for Lambda functions."""
import os

import boto3


def setup_environment() -> None:
    """Set up environment variables needed by Lambda functions."""
    # Set up SSL certificate path if not already set
    if "SSL_CERT_FILE" not in os.environ:
        # Default to the Amazon root CA bundle location in Lambda
        os.environ["SSL_CERT_FILE"] = "/etc/pki/tls/certs/ca-bundle.crt"

    # Set up any other common environment variables here
    if "AWS_REGION" not in os.environ:
        session = boto3.Session()
        os.environ["AWS_REGION"] = session.region_name or "us-east-1"


# Run setup when module is imported
setup_environment()
