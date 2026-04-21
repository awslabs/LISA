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

"""Unit tests for golden dataset types and loading."""

import json

import pytest
from lisapy.evaluation import GoldenDatasetEntry, load_golden_dataset
from pydantic import ValidationError


class TestGoldenDatasetEntry:
    """Tests for GoldenDatasetEntry Pydantic model validation."""

    def test_valid_entry(self):
        entry = GoldenDatasetEntry(
            query="What is SCORE?",
            expected=["score"],
            relevance={"score": 3},
            type="semantic",
        )
        assert entry.query == "What is SCORE?"
        assert entry.expected == ["score"]
        assert entry.relevance == {"score": 3}
        assert entry.type == "semantic"

    def test_extra_fields_allowed(self):
        """Adversarial queries have a 'note' field — extra fields should be accepted."""
        entry = GoldenDatasetEntry(
            query="convergence rates",
            expected=["gp_nn"],
            relevance={"gp_nn": 3},
            type="adversarial",
            note="Should NOT return conformal paper",
        )
        assert entry.note == "Should NOT return conformal paper"

    def test_empty_expected_valid(self):
        """Negative queries have empty expected and relevance."""
        entry = GoldenDatasetEntry(
            query="What is the recipe for cookies?",
            expected=[],
            relevance={},
            type="negative",
        )
        assert entry.expected == []
        assert entry.relevance == {}


class TestLoadGoldenDataset:
    """Tests for load_golden_dataset() — JSONL loading with validation."""

    def test_load_valid_jsonl(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        entries = [
            {"query": "q1", "expected": ["a"], "relevance": {"a": 3}, "type": "semantic"},
            {"query": "q2", "expected": ["b", "c"], "relevance": {"b": 3, "c": 1}, "type": "lexical"},
            {"query": "q3", "expected": [], "relevance": {}, "type": "negative"},
        ]
        jsonl.write_text("\n".join(json.dumps(e) for e in entries))
        result = load_golden_dataset(str(jsonl))
        assert len(result) == 3
        assert all(isinstance(e, GoldenDatasetEntry) for e in result)
        assert result[0].query == "q1"
        assert result[2].type == "negative"

    def test_load_skips_blank_lines(self, tmp_path):
        jsonl = tmp_path / "blanks.jsonl"
        content = (
            '{"query": "q1", "expected": ["a"], "relevance": {"a": 3}, "type": "semantic"}\n'
            "\n"
            '{"query": "q2", "expected": ["b"], "relevance": {"b": 2}, "type": "lexical"}\n'
            "\n"
        )
        jsonl.write_text(content)
        result = load_golden_dataset(str(jsonl))
        assert len(result) == 2

    def test_load_validates_entries(self, tmp_path):
        """Invalid entry (missing 'query') should raise ValidationError."""
        jsonl = tmp_path / "invalid.jsonl"
        jsonl.write_text('{"expected": ["a"], "relevance": {"a": 3}}\n')
        with pytest.raises(ValidationError):
            load_golden_dataset(str(jsonl))

    def test_load_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_golden_dataset("/nonexistent/path/to/dataset.jsonl")

    def test_load_empty_file(self, tmp_path):
        jsonl = tmp_path / "empty.jsonl"
        jsonl.write_text("")
        result = load_golden_dataset(str(jsonl))
        assert result == []
