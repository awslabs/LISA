# LLM Inference Solution for Amazon Dedicated Cloud (LISA)

[![Full Documentation](https://img.shields.io/badge/Full%20Documentation-blue?style=for-the-badge&logo=Vite&logoColor=white)](https://awslabs.github.io/LISA/)

## What is LISA?

LISA is an infrastructure-as-code solution providing scalable, low latency access to customers’ generative LLMs and
embedding language models. LISA accelerates and supports customers’ GenAI experimentation and adoption, particularly in
regions where Amazon Bedrock is not available. LISA allows customers to move quickly rather than independently solve the
undifferentiated heavy lifting of hosting and inference architecture. Customers deploy LISA into a single AWS account
and integrate it with an identity provider. Customers bring their own models to LISA for self-hosting and inference
supported by Amazon Elastic Container Service (ECS). Model configuration is managed through LISA’s model management
APIs.

As use cases and model requirements grow, customers can configure LISA with external model providers. Through OpenAI's
API spec via the LiteLLM proxy, LISA is compatible with 100+ models from various providers, including Amazon Bedrock and
Amazon Jumpstart. LISA customers can centralize communication across many model providers via LiteLLM, leveraging LISA
for model orchestration. Using LISA as a model orchestration layer allows customers to standardize integrations with
externally hosted models in a single place. Without an orchestration layer, customers must individually manage unique
API integrations with each provider.

## Key Features

* **Self Host Models:** Bring your own text generation and embedding models to LISA for hosting and inference.
* **Model Orchestration:** Centralize and standardize configuration with 100+ models from model providers via LiteLLM,
  including Amazon Bedrock models.
* **Chatbot User Interface:** Through the chatbot user interface, users can prompt LLMs, receive responses, modify prompt
  templates, change model arguments, and manage their session history. Administrators can control available features via
  the configuration page.
* **Retrieval-augmented generation (RAG):** RAG reduces the need for fine-tuning, an expensive and time-consuming
  undertaking, and delivers more contextually relevant outputs. LISA offers RAG through Amazon OpenSearch or
  PostgreSQL’s PGVector extension on Amazon RDS.
* **Non-RAG Model Context:** Users can upload documents to their chat sessions to enhance responses or support use cases
  like document summarization.
* **Model Management:** Administrators can add, remove, and update models configured with LISA through the model management
  configuration page or APIs.
* **OpenAI API spec:** LISA can be configured with compatible tooling. For example, customers can configure LISA as the
  model provider for the [Continue](https://www.continue.dev/) plugin, an open-source AI code assistance for JetBrains and Visual Studio Code
  integrated development environments (IDEs). This allows users to select from any LISA-configured model to support LLM
  prompting directly in their IDE.
* **Libraries:** If your workflow includes libraries such as [LangChain](https://python.langchain.com/)
  or [OpenAI](https://github.com/openai/openai-python), then you can place LISA in your
  application by changing only the endpoint and headers for the client objects.
* **FedRAMP:** The AWS services that LISA leverages are FedRAMP High compliant.
* **Ongoing Releases:** We offer on-going release with new functionality. LISA’s roadmap is customer driven.

## Deployment Prerequisites

### Pre-Deployment Steps

* Set up and have access to an AWS account with appropriate permissions
    * All the resource creation that happens as part of CDK deployments expects Administrator or Administrator-like
      permissions with resource creation and mutation permissions. Installation will not succeed if this profile does
      not have permissions to create and edit arbitrary resources for the system. Note: This level of permissions is not
      required for the runtime of LISA. This is only necessary for deployment and subsequent updates.
* Familiarity with AWS Cloud Development Kit (CDK) and infrastructure-as-code principles
* Optional: If using the chat UI, Have your Identity Provider (IdP) information and access
* Optional: Have your VPC information available, if you are using an existing one for your deployment
* Note: CDK and Model Management both leverage AWS Systems Manager Agent (SSM) parameter store. Confirm that SSM is approved for use by your organization before beginning.

### Software

* AWS CLI installed and configured
* Python 3.9 or later
* Node.js 14 or later
* Docker installed and running
* Sufficient disk space for model downloads and conversions


## Getting Started

For detailed instructions on setting up, configuring, and deploying LISA, please refer to our separate documentation on
installation and usage.

- [Deployment Guide](lib/docs/admin/getting-started.md)
- [Configuration](lib/docs/config/configuration.md)

## License

Although this repository is released under the Apache 2.0 license, when configured to use PGVector as a RAG store it
uses
the third party `psycopg2-binary` library. The `psycopg2-binary` project's licensing includes
the [LGPL with exceptions](https://github.com/psycopg/psycopg2/blob/master/LICENSE) license.
