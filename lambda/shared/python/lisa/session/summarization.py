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

"""Pure helpers for building the summarization prompt fed to the LLM during
session compaction. Kept side-effect-free so they can be unit-tested without
DynamoDB or HTTP plumbing.
"""

import json
from typing import Any

_ROLE_LABELS = {
    "human": "USER",
    "ai": "ASSISTANT",
    "system": "SYSTEM",
    "tool": "TOOL_RESULT",
    "summary": "PREVIOUS_SUMMARY",
}


def format_messages_for_summary(messages: list[dict[str, Any]]) -> str:
    """Render a list of session messages as a readable transcript for the LLM."""
    lines = []
    for msg in messages:
        msg_type = msg.get("type", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [
                item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
            ]
            content = "\n".join(text_parts)
        if not isinstance(content, str):
            content = str(content)

        role_label = _ROLE_LABELS.get(msg_type, msg_type.upper())
        lines.append(f"[{role_label}]: {content}")

        if msg.get("toolCalls"):
            for tc in msg["toolCalls"]:
                tc_name = tc.get("name", "unknown") if isinstance(tc, dict) else "unknown"
                tc_args = tc.get("args", {}) if isinstance(tc, dict) else {}
                lines.append(f"  [TOOL_CALL]: {tc_name}({json.dumps(tc_args, default=str)})")

    return "\n\n".join(lines)


def build_summary_prompt(conversation_text: str) -> str:
    """Build the user-side prompt for the summarizer."""
    return (
        "Summarize the following conversation into a concise but comprehensive summary.\n\n"
        "PRIMARY FOCUS: The [USER] and [ASSISTANT] turns are the signal. Capture what the "
        "user asked, what the assistant concluded, and what they decided together. "
        "Treat everything else as supporting context that should NOT be reproduced verbatim.\n\n"
        "PRESERVE:\n"
        "1. The user's stated goals, questions, preferences, and constraints\n"
        "2. The assistant's conclusions, recommendations, and answers\n"
        "3. Decisions reached and any open questions left unresolved\n"
        "4. Tool calls and their outcomes (tool name, why it was called, what was learned) — "
        "summarize results, do not paste them\n"
        "5. Errors encountered and how they were resolved\n"
        "6. Specific file paths, identifiers, or values ONLY when the user or assistant "
        "actively referenced or reasoned about them in the dialogue\n\n"
        "DO NOT INCLUDE:\n"
        "- Verbatim file context, document excerpts, or 'Context from document search:' blocks "
        "that were injected into user messages — these are retrieval artifacts, not conversation. "
        "If a RAG/document lookup was performed, note at most that it occurred and what high-level "
        "finding it produced, and skip it entirely if the assistant did not act on it.\n"
        "- Code snippets or configuration dumps that appeared as input context but were never "
        "discussed by the assistant\n"
        "- Conversational pleasantries or redundant back-and-forth\n\n"
        "FORMAT: Structured narrative with sections for multiple topics. "
        "Use bullet points for facts and decisions. Favor information density over completeness — "
        "a shorter summary that captures the dialogue is better than a longer one padded with context.\n\n"
        f"CONVERSATION:\n{conversation_text}"
    )
