# #   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# #
# #   Licensed under the Apache License, Version 2.0 (the "License").
# #   You may not use this file except in compliance with the License.
# #   You may obtain a copy of the License at
# #
# #       http://www.apache.org/licenses/LICENSE-2.0
# #
# #   Unless required by applicable law or agreed to in writing, software
# #   distributed under the License is distributed on an "AS IS" BASIS,
# #   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# #   See the License for the specific language governing permissions and
# #   limitations under the License.

# """Test basic usage of the Lisapy SDK."""
# from typing import Union

# import pytest
# from lisapy import LisaLlm
# from lisapy.errors import NotFoundError
# from lisapy.types import ModelKwargs, ModelType

# class LisaLlmTest:

#     client: LisaLlm

#     def setup():
#         client = LisaLlm(url=url, verify=verify, headers=headers)

# @pytest.mark.skip(reason="Model not deployed")
# def test_list_textgen_tgi_models(url: str, verify: Union[bool, str], headers: dict) -> None:
#     """Test to see if we can retrieve textgen TGI models."""
#     client = LisaLlm(url=url, verify=verify, headers=headers)
#     models = client.list_textgen_models()

#     assert all(m.model_type == ModelType.TEXTGEN for m in models)
#     assert all(hasattr(m, "streaming") for m in models)

#     tgi_models = [m for m in models if m.provider == "ecs.textgen.tgi"]
#     tgi_model = tgi_models[0]

#     assert isinstance(tgi_model.model_kwargs, ModelKwargs)
#     assert hasattr(tgi_model.model_kwargs, "max_new_tokens")
#     assert hasattr(tgi_model.model_kwargs, "top_k")
#     assert hasattr(tgi_model.model_kwargs, "top_p")
#     assert hasattr(tgi_model.model_kwargs, "do_sample")
#     assert hasattr(tgi_model.model_kwargs, "temperature")
#     assert hasattr(tgi_model.model_kwargs, "repetition_penalty")
#     assert hasattr(tgi_model.model_kwargs, "return_full_text")
#     assert hasattr(tgi_model.model_kwargs, "truncate")
#     assert hasattr(tgi_model.model_kwargs, "stop_sequences")
#     assert hasattr(tgi_model.model_kwargs, "seed")
#     assert hasattr(tgi_model.model_kwargs, "do_sample")
#     assert hasattr(tgi_model.model_kwargs, "watermark")


# @pytest.mark.skip(reason="Model not deployed")
# def test_generate_tgi(url: str, verify: Union[bool, str], headers: dict) -> None:
#     """Generates minimal response from textgen.tgi model in batch mode."""
#     client = LisaLlm(url=url, verify=verify, headers=headers)
#     text_gen_models = client.list_textgen_models()
#     model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
#     model.model_kwargs.max_new_tokens = 1
#     response = client.generate("test", model)

#     # assert response.generated_text == ''
#     assert response.generated_tokens == 1
#     assert response.finish_reason == "length"


# def test_model_not_found(url: str, verify: Union[bool, str], headers: dict) -> None:
#     """Attempts to describe a model that doesn't exist."""
#     client = LisaLlm(url=url, verify=verify, headers=headers)
#     with pytest.raises(NotFoundError):
#         client.describe_model(provider="unknown.provider", model_name="model-name")


# @pytest.mark.skip(reason="Model not deployed")
# def test_embed_instructor(url: str, verify: Union[bool, str], headers: dict) -> None:
#     """Generates a simple embedding from the instructor embedding model."""
#     client = LisaLlm(url=url, verify=verify, headers=headers)
#     embedding_models = client.list_embedding_models()
#     model = [m for m in embedding_models if m.provider == "ecs.embedding.instructor"][0]
#     print(model)
#     embedding = client.embed("test", model)

#     assert isinstance(embedding, list)
#     assert isinstance(embedding[0], list)
#     assert isinstance(embedding[0][0], float)


# def test_generate_stream(url: str, verify: Union[bool, str], headers: dict) -> None:
#     """Generates a streaming response from a textgen.tgi model."""
#     client = LisaLlm(url=url, verify=verify, headers=headers)
#     text_gen_models = client.list_textgen_models()
#     model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
#     model.model_kwargs.max_new_tokens = 1
#     responses = list(client.generate_stream("what is deep learning?", model=model))

#     assert len(responses) == 1
#     response = responses[0]

#     assert response.token == ""
#     assert response.finish_reason == "length"
#     assert response.generated_tokens == 1


# @pytest.mark.asyncio
# async def test_generate_async(url: str, verify: Union[bool, str], headers: dict) -> None:
#     """Generates a batch async response from a textgen.tgi model."""
#     client = LisaLlm(url=url, verify=verify, headers=headers)
#     text_gen_models = client.list_textgen_models()
#     model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
#     model.model_kwargs.max_new_tokens = 1
#     response = await client.agenerate("test", model=model)

#     assert response.finish_reason == "length"
#     assert response.generated_tokens == 1


# @pytest.mark.asyncio
# async def test_generate_stream_async(url: str, verify: Union[bool, str], headers: dict) -> None:
#     """Generates a streaming async response from a textgen.tgi model."""
#     client = LisaLlm(url=url, verify=verify, headers=headers)
#     text_gen_models = client.list_textgen_models()
#     model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
#     model.model_kwargs.max_new_tokens = 1
#     responses = [response async for response in client.agenerate_stream("what is deep learning?", model=model)]

#     assert len(responses) == 1
#     response = responses[0]

#     assert response.token == ""
#     assert response.finish_reason == "length"
#     assert response.generated_tokens == 1

# """
# # List models
#     "models",
#     "v1/models",
#     # Model Info
#     "model/info" "v1/model/info"
#     # Text completions
#     "chat/completions",
#     "v1/chat/completions",
#     "completions",
#     "v1/completions",
#     # Embeddings
#     "embeddings",
#     "v1/embeddings",
#     # Create images
#     "images/generations",
#     "v1/images/generations",
#     # Audio routes
#     "audio/speech",
#     "v1/audio/speech",
#     "audio/transcriptions",
#     "v1/audio/transcriptions",
#     # Health check routes
#     "health",
#     "health/readiness",
#     "health/liveliness",
#     """
