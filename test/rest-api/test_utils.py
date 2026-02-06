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

"""Unit tests for REST API utilities."""

import sys
from pathlib import Path

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))

from utils.cache_manager import (
    get_registered_models_cache,
    set_registered_models_cache,
)
from utils.decorators import singleton
from utils.resources import ModelType, RestApiResource


class TestCacheManager:
    """Test suite for cache_manager module."""

    def test_set_and_get_cache(self):
        """Test setting and getting cache."""
        test_cache = {
            ModelType.EMBEDDING: {"provider1": ["model1"]},
            ModelType.TEXTGEN: {"provider2": ["model2"]},
            "metadata": {},
            "endpointUrls": {},
        }

        set_registered_models_cache(test_cache)
        result = get_registered_models_cache()

        assert result == test_cache

    def test_get_cache_empty(self):
        """Test getting cache when empty."""
        # Reset cache
        set_registered_models_cache({})
        result = get_registered_models_cache()

        assert result == {}

    def test_cache_persistence(self):
        """Test that cache persists across multiple gets."""
        test_cache = {"test": "data"}

        set_registered_models_cache(test_cache)

        result1 = get_registered_models_cache()
        result2 = get_registered_models_cache()

        assert result1 == result2 == test_cache

    def test_cache_update(self):
        """Test updating cache."""
        initial_cache = {"key1": "value1"}
        updated_cache = {"key1": "value1", "key2": "value2"}

        set_registered_models_cache(initial_cache)
        assert get_registered_models_cache() == initial_cache

        set_registered_models_cache(updated_cache)
        assert get_registered_models_cache() == updated_cache


class TestSingletonDecorator:
    """Test suite for singleton decorator."""

    def test_singleton_creates_single_instance(self):
        """Test that singleton decorator creates only one instance."""

        @singleton
        class TestClass:
            def __init__(self):
                self.value = 0

        instance1 = TestClass()
        instance2 = TestClass()

        assert instance1 is instance2

    def test_singleton_preserves_state(self):
        """Test that singleton preserves state across calls."""

        @singleton
        class Counter:
            def __init__(self):
                self.count = 0

            def increment(self):
                self.count += 1

        counter1 = Counter()
        counter1.increment()

        counter2 = Counter()
        counter2.increment()

        assert counter1.count == 2
        assert counter2.count == 2
        assert counter1 is counter2

    def test_singleton_with_different_classes(self):
        """Test that different classes get different singleton instances."""

        @singleton
        class ClassA:
            pass

        @singleton
        class ClassB:
            pass

        instance_a = ClassA()
        instance_b = ClassB()

        assert instance_a is not instance_b
        assert not isinstance(instance_a, type(instance_b))


class TestResources:
    """Test suite for resources module."""

    def test_model_type_enum(self):
        """Test ModelType enum values."""
        assert ModelType.EMBEDDING == "embedding"
        assert ModelType.TEXTGEN == "textgen"

    def test_rest_api_resource_enum(self):
        """Test RestApiResource enum values."""
        assert RestApiResource.EMBEDDINGS == "embeddings"
        assert RestApiResource.GENERATE == "generate"
        assert RestApiResource.GENERATE_STREAM == "generateStream"

    def test_model_type_string_comparison(self):
        """Test that ModelType can be compared with strings."""
        assert ModelType.EMBEDDING == "embedding"
        assert ModelType.TEXTGEN == "textgen"

    def test_rest_api_resource_string_comparison(self):
        """Test that RestApiResource can be compared with strings."""
        assert RestApiResource.EMBEDDINGS == "embeddings"
        assert RestApiResource.GENERATE == "generate"
        assert RestApiResource.GENERATE_STREAM == "generateStream"
