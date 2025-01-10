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

"""Test basic usage of the Lisapy SDK."""
import logging
from typing import Union

from lisapy import LisaLlm


def test_list_models(url: str, verify: Union[bool, str], headers: dict) -> None:
    client = LisaLlm(url=url, verify=verify, headers=headers)
    models = client.list_models()
    logging.info(f"Found {len(models)} models - {models}")
    assert len(models) > 0


def test_describe_models(url: str, verify: Union[bool, str], headers: dict) -> None:
    client = LisaLlm(url=url, verify=verify, headers=headers)
    models = client.describe_model(model_name="")
    logging.info(f"Found {len(models)} models - {models}")
    assert len(models) > 0
