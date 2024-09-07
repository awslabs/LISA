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

"""Utility functions to support using LISA with third-party clients."""

import os
import tempfile
from typing import Any


def get_cert_path(iam_client: Any) -> str | bool:
    """Get cert path for IAM certs for SSL validation against LISA Serve endpoint."""
    # If no SSL Cert ARN is specified just default verify to true and the cert will need to be
    # signed by a known CA
    # Assume cert is signed with known CA if coming from ACM
    cert_arn = os.environ.get("RESTAPI_SSL_CERT_ARN", "")
    if not cert_arn or cert_arn.split(":")[2] == "acm":
        return True

    # We have the arn but we need the name which is the last part of the arn
    rest_api_cert = iam_client.get_server_certificate(ServerCertificateName=cert_arn.split("/")[1])
    cert_body = rest_api_cert["ServerCertificate"]["CertificateBody"]
    cert_file = tempfile.NamedTemporaryFile(delete=False)
    cert_file.write(cert_body.encode("utf-8"))
    rest_api_cert_path = cert_file.name

    return rest_api_cert_path
