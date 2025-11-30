# LLM Inference Solution for Amazon Dedicated Cloud (LISA)
[![Full Documentation](https://img.shields.io/badge/Full%20Documentation-blue?style=for-the-badge&logo=Vite&logoColor=white)](https://awslabs.github.io/LISA/)
[![Contact Us](https://img.shields.io/badge/Contact%20Us-green?style=for-the-badge&logo=maildotru&logoColor=white)](mailto:lisa-product-team@amazon.com)
## What is LISA?
Our large language model (LLM) inference solution for the Amazon Dedicated Cloud (ADC), LISA, is open source infrastructure-as-code. Customers deploy it directly into an Amazon Web Services (AWS) account in any region. LISA is scalable and ready to support production use cases.

LISA accelerates GenAI adoption by offering built-in configurability with Amazon Bedrock models, Knowledge Bases, and Guardrails. Also by offering advanced capabilities like an optional enterprise-ready chat user interface (UI) with configurable features, authentication, resource access control, centralized model orchestration via LiteLLM, model self-hosting via Amazon ECS, retrieval augmented generation (RAG), APIs, and broad model context protocol (MCP) support and features. LISA is also compatible with OpenAI’s API specification making it easily configurable with supporting solutions. For example, the Continue plugin for VSCode and JetBrains integrated development environments (IDE).

LISA's roadmap is customer-driven, with new capabilities launching monthly. Reach out to the product team to ask questions, provide feedback, and send feature requests via the "Contact Us" button above.

## Key Features
* **Open Source**: No subscription or licensing fees. LISA costs are based on service usage.
* **Ongoing Releases**: The product roadmap is customer-driven with releases typically every 2-4 weeks. LISA is backed by a software development team that builds production grade solutions to accelerate customers' GenAI adoption.
* **Model Flexibility**: Bring your own models for self-hosting, or quickly configure LISA with 100+ models supported by third-party model providers, including Amazon Bedrock and Jumpstart.
* **Model Orchestration**: Centralize and standardize unique API calls to third-party model providers automatically with LISA via LiteLLM. LISA standardizes the unique API calls into the OpenAI format automatically. All that is required is an API key, model name, and API endpoint.
* **Modular Components**: Accelerate GenAI adoption with secure, scalable software. LISA supports various use cases through configurable components: model serving and orchestration, chat user interface with advanced capabilities, authentication, retrieval augmented generation (RAG), Anthropic’s Model Context Protocol (MCP), and APIs.
* **CodeGen**: LISA supports OpenAI’s API specification, making it easily configurable with compatible solutions like the Continue plugin for VSCode and JetBrains IDEs.
* **FedRAMP**: Leverages FedRAMP High compliant services.

## Major Components
LISA’s four major components include Serve, a Chat UI, RAG, and MCP. LISA Serve and LISA MCP are standalone, foundational core solutions with APIs for customers not leveraging LISA’s Chat UI. Both LISA’s Chat UI and RAG are optional components, but must be used with Serve.

Read more in the Architecture Overview section of LISA's documentation site linked above.

## Deployment Prerequisites
### Pre-Deployment Steps
* Set up or have access to an AWS account.
* Ensure that your AWS account has the appropriate permissions. Resource creation during the AWS CDK deployment expects Administrator or Administrator-like permissions, to include resource creation and mutation permissions. Installation will not succeed if this profile does not have permissions to create and edit arbitrary resources for the system. This level of permissions is not required for the runtime of LISA. This is only necessary for deployment and subsequent updates.
* If using the chat UI, have your Identity Provider (IdP) information available, and access.
* If using an existing VPC, have its information available.
* Familiarity with AWS Cloud Development Kit (CDK) and infrastructure-as-code principles is a plus.
* AWS CDK and Model Management both leverage AWS Systems Manager Agent (SSM) parameter store. Confirm that SSM is approved for use by your organization before beginning. If you're new to CDK, review the [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/v2/guide/home.html) and consult with your AWS support team.
### Software
* AWS CLI installed and configured
* Python 3.11
* Node.js 20
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
