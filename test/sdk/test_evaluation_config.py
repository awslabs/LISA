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

"""Unit tests for evaluation config loading."""

import textwrap

import pytest
from lisapy.evaluation.config import (
    LisaApiBackend,
    load_eval_config,
)
from pydantic import ValidationError

VALID_CONFIG_YAML = textwrap.dedent(
    """\
    region: us-east-2
    k: 5

    documents:
      pallet: "Pallet verification.pdf"
      score: "score_pdf_parsing.pdf"

    backends:
      bedrock_kb:
        - name: "Bedrock KB"
          knowledge_base_id: "CFXEDCEHAQ"
          s3_bucket: "s3://bedrock-bucket"

      lisa_api:
        - name: "OpenSearch"
          api_url: "https://api.example.com/dev"
          deployment_name: "lisa-dev"
          repo_id: "opensearch-test"
          collection_id: "default"
          s3_bucket: "s3://os-bucket"

        - name: "PGVector"
          api_url: "https://api.example.com/dev"
          deployment_name: "lisa-dev"
          repo_id: "pgvector-repo"
          collection_id: "default"
          s3_bucket: "s3://pg-bucket"
"""
)


class TestEvalConfig:
    """Tests for EvalConfig Pydantic model."""

    def test_valid_config(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_CONFIG_YAML)
        config = load_eval_config(str(cfg_file))

        assert config.region == "us-east-2"
        assert config.k == 5
        assert len(config.documents) == 2
        assert config.documents["pallet"] == "Pallet verification.pdf"

    def test_source_map_generation(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_CONFIG_YAML)
        config = load_eval_config(str(cfg_file))

        bk = config.backends.bedrock_kb[0]
        source_map = bk.build_source_map(config.documents)
        assert source_map["pallet"] == "s3://bedrock-bucket/Pallet verification.pdf"
        assert source_map["score"] == "s3://bedrock-bucket/score_pdf_parsing.pdf"

    def test_default_k(self, tmp_path):
        yaml = textwrap.dedent(
            """\
            region: us-east-1
            documents:
              doc_a: "a.pdf"
            backends:
              bedrock_kb: []
              lisa_api: []
        """
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml)
        config = load_eval_config(str(cfg_file))
        assert config.k == 5

    def test_missing_region_raises(self, tmp_path):
        yaml = textwrap.dedent(
            """\
            documents:
              doc_a: "a.pdf"
            backends:
              bedrock_kb: []
              lisa_api: []
        """
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml)
        with pytest.raises(ValidationError):
            load_eval_config(str(cfg_file))

    def test_missing_documents_raises(self, tmp_path):
        yaml = textwrap.dedent(
            """\
            region: us-east-1
            backends:
              bedrock_kb: []
              lisa_api: []
        """
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml)
        with pytest.raises(ValidationError):
            load_eval_config(str(cfg_file))

    def test_nonexistent_config_raises(self):
        with pytest.raises(FileNotFoundError):
            load_eval_config("/nonexistent/config.yaml")

    def test_bedrock_only_config(self, tmp_path):
        """Config with only Bedrock KB, no LISA API backends."""
        yaml = textwrap.dedent(
            """\
            region: us-east-2
            documents:
              doc_a: "a.pdf"
            backends:
              bedrock_kb:
                - name: "KB"
                  knowledge_base_id: "ABC123"
                  s3_bucket: "s3://bucket"
        """
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml)
        config = load_eval_config(str(cfg_file))
        assert len(config.backends.bedrock_kb) == 1
        assert config.backends.lisa_api == []


class TestLisaApiBackendValidation:
    """Tests for input validation on LisaApiBackend."""

    def _make_backend(self, **overrides) -> LisaApiBackend:
        defaults = {
            "name": "test",
            "api_url": "https://api.example.com",
            "deployment_name": "lisa-dev",
            "repo_id": "test-repo",
            "s3_bucket": "s3://bucket",
        }
        defaults.update(overrides)
        return LisaApiBackend(**defaults)

    def test_valid_https_url_accepted(self):
        backend = self._make_backend(api_url="https://api.example.com/dev")
        assert backend.api_url == "https://api.example.com/dev"

    def test_http_api_url_rejected(self):
        with pytest.raises(ValidationError, match="api_url"):
            self._make_backend(api_url="http://insecure.example.com")


class TestEvalConfigValidation:
    """Tests for k and documents validation on EvalConfig."""

    def test_k_zero_rejected(self, tmp_path):
        yaml = textwrap.dedent(
            """\
            region: us-east-1
            k: 0
            documents:
              doc_a: "a.pdf"
            backends:
              bedrock_kb: []
              lisa_api: []
        """
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml)
        with pytest.raises(ValidationError, match="k"):
            load_eval_config(str(cfg_file))

    def test_k_negative_rejected(self, tmp_path):
        yaml = textwrap.dedent(
            """\
            region: us-east-1
            k: -1
            documents:
              doc_a: "a.pdf"
            backends:
              bedrock_kb: []
              lisa_api: []
        """
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml)
        with pytest.raises(ValidationError, match="k"):
            load_eval_config(str(cfg_file))

    def test_empty_documents_rejected(self, tmp_path):
        yaml = textwrap.dedent(
            """\
            region: us-east-1
            documents: {}
            backends:
              bedrock_kb: []
              lisa_api: []
        """
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml)
        with pytest.raises(ValidationError, match="documents"):
            load_eval_config(str(cfg_file))
