# LLM Inference Solution for Amazon Dedicated Cloud (LISA)

LISA is an infrastructure-as-code solution that supports model hosting and inference for Large Language Models (LLMs).
It is designed to be deployed directly into an AWS account, allowing customers to provision their own infrastructure and
bring their own models for hosting and inference through Amazon ECS.

## Key Features

- Scalable, low-latency access to generative LLMs and embedding language models
- Chatbot user interface for experimentation and production use cases
- Integration of retrieval-augmented generation (RAG) with Amazon OpenSearch or PostgreSQL's PGVector extension
- Support for OpenAI's API Spec via the LiteLLM proxy
- Compatibility with models hosted externally by supported model providers
- Standardized model orchestration and communication across model providers

## Components

1. **LISA Model Management**: Handles model deployment and management.
2. **LISA Serve**: Manages the inference API and model serving.
3. **LISA Chat**: Provides the user interface for interacting with deployed models.

## Use Cases

- Experimenting with LLMs and developing Generative AI applications
- Hosting and serving custom or third-party language models
- Integrating LLM capabilities into existing applications and workflows

## Key Benefits

- Accelerates the use of Generative AI applications
- Reduces the need for fine-tuning by incorporating external knowledge sources
- Provides a flexible platform for model experimentation and deployment
- Offers compatibility with OpenAI-centric tooling and libraries

## Compatibility

LISA supports various model types and can be used as a stand-in replacement for applications that utilize OpenAI-centric
tooling (e.g., OpenAI's Python library, LangChain).

## Getting Started

For detailed instructions on setting up, configuring, and deploying LISA, please refer to our separate documentation on
installation and usage.

For full documentation,
visit

[![LISA Documentation](https://img.shields.io/badge/LISA%20Documentation-blue?style=for-the-badge&logo=Vite&logoColor=white)](https://awslabs.github.io/LISA/)

## License

Although this repository is released under the Apache 2.0 license, when configured to use PGVector as a RAG store it
uses
the third party `psycopg2-binary` library. The `psycopg2-binary` project's licensing includes
the [LGPL with exceptions](https://github.com/psycopg/psycopg2/blob/master/LICENSE) license.
