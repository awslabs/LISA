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

import json
import os

# Prevent lambda/models imports from failing during autouse fixtures.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("MODEL_TABLE_NAME", "model-table")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "guardrails-table")

from lisa.session.summarization import build_summary_prompt, format_messages_for_summary  # noqa: E402


def test_format_messages_renders_known_role_labels():
    messages = [
        {"type": "human", "content": "hi"},
        {"type": "ai", "content": "hello"},
        {"type": "system", "content": "be precise"},
        {"type": "tool", "content": "result"},
        {"type": "summary", "content": "previous summary text"},
    ]
    out = format_messages_for_summary(messages)
    assert "[USER]: hi" in out
    assert "[ASSISTANT]: hello" in out
    assert "[SYSTEM]: be precise" in out
    assert "[TOOL_RESULT]: result" in out
    assert "[PREVIOUS_SUMMARY]: previous summary text" in out


def test_format_messages_unknown_type_uppercased():
    messages = [{"type": "function", "content": "foo"}]
    out = format_messages_for_summary(messages)
    assert "[FUNCTION]: foo" in out


def test_format_messages_extracts_text_from_list_content():
    """Content blocks with type=text should be joined; non-text blocks dropped."""
    messages = [
        {
            "type": "human",
            "content": [
                {"type": "text", "text": "first"},
                {"type": "image_url", "image_url": {"url": "..."}},
                {"type": "text", "text": "second"},
            ],
        }
    ]
    out = format_messages_for_summary(messages)
    assert "[USER]: first\nsecond" in out
    assert "image_url" not in out


def test_format_messages_coerces_non_string_content():
    """Numbers, dicts, etc. should be stringified, not crash."""
    messages = [{"type": "human", "content": {"weird": "shape"}}]
    out = format_messages_for_summary(messages)
    assert "[USER]:" in out
    assert "weird" in out


def test_format_messages_includes_tool_calls():
    messages = [
        {
            "type": "ai",
            "content": "calling tool",
            "toolCalls": [
                {"name": "search", "args": {"query": "lisa"}},
                {"name": "fetch", "args": {"url": "x"}},
            ],
        }
    ]
    out = format_messages_for_summary(messages)
    assert "[TOOL_CALL]: search(" in out
    assert '"query": "lisa"' in out
    assert "[TOOL_CALL]: fetch(" in out


def test_format_messages_handles_malformed_tool_call():
    """Non-dict toolCalls entries should not crash; they label as unknown."""
    messages = [{"type": "ai", "content": "x", "toolCalls": ["not-a-dict"]}]
    out = format_messages_for_summary(messages)
    assert "[TOOL_CALL]: unknown(" in out


def test_format_messages_empty_input_returns_empty_string():
    assert format_messages_for_summary([]) == ""


def test_format_messages_missing_type_falls_back_to_unknown():
    messages = [{"content": "orphan"}]
    out = format_messages_for_summary(messages)
    assert "[UNKNOWN]: orphan" in out


def test_format_messages_separator_between_entries():
    """Entries are joined with a blank line separator."""
    messages = [
        {"type": "human", "content": "a"},
        {"type": "ai", "content": "b"},
    ]
    out = format_messages_for_summary(messages)
    assert "\n\n" in out


def test_build_summary_prompt_contains_required_directives():
    prompt = build_summary_prompt("USER: hi\n\nASSISTANT: hello")
    # Spot-check the critical-requirements scaffold the LLM must see
    assert "Summarize the following conversation" in prompt
    # Tool calls remain a required preservation target, but the wording softened
    # to "summarize results, do not paste them" — the bare phrase "tool call" still appears.
    assert "Tool calls" in prompt
    # RAG/document blocks are now in the DO-NOT-INCLUDE list, not the preserve list
    assert "DO NOT INCLUDE" in prompt
    assert "Context from document search" in prompt
    assert prompt.endswith("USER: hi\n\nASSISTANT: hello")


def test_build_summary_prompt_includes_conversation_text_verbatim():
    convo = "[USER]: alpha\n\n[ASSISTANT]: beta"
    prompt = build_summary_prompt(convo)
    # The conversation text must appear unchanged in the prompt body
    assert convo in prompt


def test_format_messages_tool_call_args_serialize_decimal_and_other_types():
    """default=str must let json.dumps survive non-JSON-native values."""
    from decimal import Decimal

    messages = [{"type": "ai", "content": "x", "toolCalls": [{"name": "t", "args": {"v": Decimal("1.5")}}]}]
    # Should not raise
    out = format_messages_for_summary(messages)
    # Decimal serializes via str(), producing "1.5"
    assert json.dumps({"v": Decimal("1.5")}, default=str) in out
