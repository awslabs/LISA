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

"""Unit tests for LISA SDK langchain adapters.

Note: These are simplified tests. Full integration tests with real LisaLlm
instances are better suited for integration testing due to Pydantic validation complexity.
"""

import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lisa-sdk"))

# Langchain modules that may be mocked by other tests (e.g. test_repository_lambda)
_LANGCHAIN_MODULES = [
    "langchain_core",
    "langchain_core.caches",
    "langchain_core.callbacks",
    "langchain_core.embeddings",
    "langchain_core.language_models",
    "langchain_core.outputs",
]


def _restore_langchain_modules():
    """Remove mock langchain entries from sys.modules so real imports work."""
    for mod in _LANGCHAIN_MODULES:
        sys.modules.pop(mod, None)


def test_langchain_imports():
    """Test that langchain module imports successfully."""
    _restore_langchain_modules()
    from lisapy.langchain import LisaEmbeddings, LisaOpenAIEmbeddings, LisaTextgen

    assert LisaTextgen is not None
    assert LisaOpenAIEmbeddings is not None
    assert LisaEmbeddings is not None


def test_lisa_textgen_llm_type():
    """Test LisaTextgen has correct LLM type attribute."""
    _restore_langchain_modules()
    from lisapy.langchain import LisaTextgen

    # Check class has the _llm_type method
    assert hasattr(LisaTextgen, "_llm_type")


def test_lisa_embeddings_has_embed_methods():
    """Test LisaEmbeddings has required embedding methods."""
    _restore_langchain_modules()
    from lisapy.langchain import LisaEmbeddings

    assert hasattr(LisaEmbeddings, "embed_documents")
    assert hasattr(LisaEmbeddings, "embed_query")


def test_lisa_openai_embeddings_has_embed_methods():
    """Test LisaOpenAIEmbeddings has required embedding methods."""
    _restore_langchain_modules()
    from lisapy.langchain import LisaOpenAIEmbeddings

    assert hasattr(LisaOpenAIEmbeddings, "embed_documents")
    assert hasattr(LisaOpenAIEmbeddings, "embed_query")
    assert hasattr(LisaOpenAIEmbeddings, "aembed_documents")
    assert hasattr(LisaOpenAIEmbeddings, "aembed_query")
