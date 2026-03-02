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

"""Text processing utilities - pure functions for easy testing."""


def render_context_from_messages(messages_list: list[dict[str, str]]) -> str:
    """Render context string from message list.

    Pure function that converts a list of messages into a single context string.

    Parameters
    ----------
    messages_list : List[Dict[str, str]]
        List of messages with 'content' field

    Returns
    -------
    str
        Concatenated message content
    """
    return "\n\n".join([message["content"] for message in messages_list])


def parse_model_provider_from_string(model_string: str) -> tuple[str, str]:
    """Parse model name and provider from combined string.

    Pure function that extracts model and provider from format: "model_name (provider_name)"

    Parameters
    ----------
    model_string : str
        Combined model string in format "model_name (provider_name)"

    Returns
    -------
    Tuple[str, str]
        Model name and provider name

    Raises
    ------
    ValueError
        If string format is invalid
    """
    if not model_string or "(" not in model_string or ")" not in model_string:
        raise ValueError(f"Invalid model string format: {model_string}")

    model_parts = model_string.split()
    if len(model_parts) < 2:
        raise ValueError(f"Invalid model string format: {model_string}")

    model_name = model_parts[0].strip()
    provider = model_parts[1].replace("(", "").replace(")", "").strip()

    if not model_name or not provider:
        raise ValueError(f"Invalid model string format: {model_string}")

    return model_name, provider


def map_openai_params_to_lisa(request_data: dict) -> dict:
    """Map OpenAI API parameters to LISA parameters.

    Pure function that transforms OpenAI request format to LISA format.

    Parameters
    ----------
    request_data : dict
        OpenAI-format request data

    Returns
    -------
    dict
        Mapped parameters for LISA
    """
    # Mapping of OpenAI params to TGI/LISA params
    param_mapping = {
        "echo": "return_full_text",
        "frequency_penalty": "repetition_penalty",
        "max_tokens": "max_new_tokens",
        "seed": "seed",
        "stop": "stop_sequences",
        "temperature": "temperature",
        "top_p": "top_p",
    }

    return {
        param_mapping[k]: request_data[k] for k in param_mapping if k in request_data and request_data[k] is not None
    }
