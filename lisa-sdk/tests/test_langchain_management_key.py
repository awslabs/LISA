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

import os
import unittest
from unittest.mock import Mock, patch

from lisapy.langchain import LisaOpenAIEmbeddings


class TestLisaOpenAIEmbeddingsManagementKey(unittest.TestCase):
    @patch.dict(os.environ, {"AWS_REGION": "us-west-2", "MANAGEMENT_KEY_SECRET_NAME_PS": "/test/secret"})
    @patch("boto3.client")
    def test_from_management_key(self, mock_boto3_client: Mock) -> None:
        # Mock SSM and Secrets Manager clients
        mock_ssm = Mock()
        mock_secrets = Mock()

        mock_boto3_client.side_effect = lambda service, **kwargs: {"ssm": mock_ssm, "secretsmanager": mock_secrets}[
            service
        ]

        # Mock SSM parameter response
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-secret-name"}}

        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {"SecretString": "test-management-token"}

        # Test the method
        embeddings = LisaOpenAIEmbeddings.from_management_key(
            lisa_openai_api_base="https://api.test.com", model="test-model", verify=True
        )

        # Verify the result
        self.assertEqual(embeddings.lisa_openai_api_base, "https://api.test.com")
        self.assertEqual(embeddings.model, "test-model")
        self.assertEqual(embeddings.api_token, "test-management-token")
        self.assertEqual(embeddings.verify, True)

        # Verify AWS calls
        mock_ssm.get_parameter.assert_called_once_with(Name="/test/secret")
        mock_secrets.get_secret_value.assert_called_once_with(SecretId="test-secret-name")


if __name__ == "__main__":
    unittest.main()
