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

from lisapy import LisaApi


# Model operations
def test_list_models(lisa_api: LisaApi) -> None:
    models = lisa_api.list_models()
    logging.info(f"Found {len(models)} models - {models}")
    assert len(models) > 0


def test_list_embedding_models(lisa_api: LisaApi) -> None:
    models = lisa_api.list_embedding_models()
    logging.info(f"Found {len(models)} models - {models}")
    assert len(models) > 0


def test_swagger_docs(lisa_api: LisaApi) -> None:
    text = lisa_api.list_docs()
    logging.info("Retrieved swagger docs")
    assert len(text) > 0


# RAG operations
def test_list_repositories(lisa_api: LisaApi) -> None:
    repos = lisa_api.list_repositories()
    logging.info(f"Found {len(repos)} repos - {repos}")
    assert len(repos) > 0


# Configs
def test_get_configs(lisa_api: LisaApi) -> None:
    configs = lisa_api.get_configs()
    logging.info(f"Found {len(configs)} configs - {configs}")
    assert len(configs) > 0


# Session
def test_list_sessions(lisa_api: LisaApi) -> None:
    sessions = lisa_api.list_sessions()
    logging.info(f"Found {len(sessions)} sessions - {sessions}")
    assert isinstance(sessions, list)
