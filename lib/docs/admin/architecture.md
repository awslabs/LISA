# Architecture Overview

LISA’s major components include Serve, a Chat user interface (UI), retrieval augmented generation (RAG), and model context protocol (MCP).
LISA Serve and LISA MCP are standalone core products and the remaining components are optional. LISA also offers APIs for customers using LISA for model hosting and orchestration.

* **Serve:** This is the core of inference with LISA. Serve supports model self-hosting in scalable Amazon ECS clusters.
Through LiteLLM, Serve is also compatible with 100+ models hosted by external model providers like Amazon Bedrock.
* **MCP:** This is the core of self-hosting MCP Servers in a scaleable entriprise ready way. LISA MCP supports hosting STDIO/HTTP/SSE servers in ECS Fargate clusters with custom images or prebuilt images. It also supports copying in custom resources for hosting via S3.
* **Chat UI:** Customers prompt LLMs, receive responses, create and modify prompt templates and personas, adjust model
arguments, use advanced features like RAG and MCP, manage session history, export conversations and images, upload files to vector stores, and upload files for non-RAG in context references. Administrators can add, remove, and update models. They can control chat features available to customers without requiring code changes or application re-deployment. Administrators can set up vector stores and document ingestion pipelines to support RAG. The chat UI also offers user authentication. Administrators configure LISA with their identity provider (IdP). Out of the box LISA supports the OIDC protocol.
* **RAG:** LISA is compatible with Amazon OpenSearch, Bedrock Knowledge Bases, and PostgreSQL's PGVector extension in Amazon RDS. LISA offers document ingestion with LangChain, this also includes automated pipelines for customers to routinely load files into their vector stores.
* **APIs:** Customers leveraging LISA for model hosting and orchestration can integrate LISA with existing mission
tooling or alternative front ends. LISA uses Amazon DynamoDB to store Tokens to interact with the exposed APIs.
  * Inference requests through LiteLLM support prompting LLMs configured with LISA. Prompts can support LISA’s RAG and
    MCP and features.
  * Chat session API supports session history, conversation continuity and management.
  * Model management API supports deploying, updating, and deleting third party and internally hosted models.


## Serve
![LISA Serve Architecture](../assets/LisaServe.png)

LISA Serve is the foundational, core component of the inference solution. It provides model self-hosting and integration with
compatible external model providers. Serve supports text generation, image generation, and embedding models. Serve’s
components are designed for scale and reliability. Serve can be accessed via LISA’s REST APIs, or through LISA’s chat
user interface (UI). Regardless of origin, all inference requests are routed via an Application Load Balancer (ALB),
which serves as the main entry point to LISA Serve. The ALB forwards requests through the LiteLLM proxy, hosted in its
own scalable Amazon Elastic Container Service (ECS) cluster with Amazon Elastic Compute Cloud (EC2) instance. LiteLLM
routes traffic to the appropriate model.

Self-hosted model traffic is directed to model specific ALBs, which enable autoscaling in the event of heavy traffic.
Each self-hosted model has their own Amazon ECS cluster and Amazon EC2 instance. Text generation and image generation
models compatible with Hugging Face’s
[Text Generation Inference (TGI)](https://huggingface.co/docs/text-generation-inference/en/index) and
[vLLM](https://docs.vllm.ai/en/latest/) images are supported. Embedding models compatible with Huffing Face’s
[Text Embedding Inference (TEI)](https://huggingface.co/docs/text-embeddings-inference/en/index) and
[vLLM](https://docs.vllm.ai/en/latest/) images are also supported. LISA uses **** S3 for loading the model weights.

**Technical Notes:**

* RAG operations are managed through `lambda/rag/lambda_functions.py`, which handles embedding generation and document
retrieval via OpenSearch and PostgreSQL.
* Direct requests to the LISA Serve ALB entrypoint must utilize the OpenAI API spec, which we support through the use
* of the LiteLLM proxy.

## MCP
![LISA MCP Architecture](../assets/LisaMcp.png)

LISA MCP is a standalone core product that provides scalable infrastructure for deploying and hosting Model Context Protocol (MCP) servers. It enables customers to self-host MCP servers in an enterprise-ready, scalable way. LISA MCP can be deployed independently of LISA Serve or configured to work seamlessly with LISA Serve and the Chat UI.

Each MCP server deployed via LISA MCP is provisioned on AWS Fargate via Amazon ECS, fronted by Application Load Balancers (ALBs) and Network Load Balancers (NLBs), and published through the existing API Gateway. This architecture allows chat sessions to securely invoke MCP tools without leaving your VPC. All routes remain protected by the same API Gateway Lambda authorizer patterns that guards the rest of LISA, ensuring API Keys, IDP lockdown, and JWT group enforcement continue to apply automatically.

**Server Types:** LISA MCP supports three MCP server types:
* **STDIO servers:** Automatically wrapped with `mcp-proxy` and exposed over HTTP on port 8080
* **HTTP servers:** Direct HTTP endpoints using the configured port (default 8000)
* **SSE servers:** Server-Sent Events endpoints for streaming responses

**Networking Architecture:** The networking follows a layered approach:
* **API Gateway** receives MCP traffic on `/mcp/{serverId}` routes
* **Network Load Balancer (NLB)** terminates the API Gateway VPC Link and forwards to the Application Load Balancer
* **Application Load Balancer (ALB)** provides HTTP features including health checks, routing, and load balancing
* **ECS Fargate Service** hosts the MCP server containers within your VPC using the same subnets and security groups as the MCP API stack

**Lifecycle Management:** AWS Step Functions orchestrate the complete lifecycle of MCP servers, handling creation, update, deletion, start, and stop workflows. Each workflow provisions the required resources using CloudFormation templates, which manage infrastructure components like ECS Fargate services, load balancers, VPC Links, and auto-scaling configurations.

**Key Features:**
* Turn-key hosting for STDIO, HTTP, or SSE MCP servers with a single API/UI workflow
* Dynamic container builds from pre-built images or S3 artifacts synced at deploy time
* Auto-scaling with configurable Fargate min/max capacity, custom metrics, and scaling targets per server
* Secure VPC networking with private ALB for internal traffic and NLB + VPC Link for API Gateway access
* Group-aware routing to limit server visibility to specific identity provider groups or make them public
* External integrations via API Gateway URLs, enabling trusted third-party agents, copilots, or workflow engines to invoke hosted MCP servers using the same credentials and auth controls

**Technical Notes:**

* MCP Server Lifecycle: Lifecycle operations such as create, update, delete, start, and stop are orchestrated by Step Functions workflows (`CreateMcpServer`, `UpdateMcpServer`, `DeleteMcpServer`). The MCP API Handler Lambda validates requests and manages server metadata in DynamoDB.
* CloudFormation: Infrastructure components are provisioned using CloudFormation templates synthesized by the MCP server deployer Lambda, as defined in `mcp_server_deployer/src/lib/ecsMcpServer.ts`.
* ECS Fargate: Each MCP server runs in its own ECS Fargate cluster with dedicated ALB and NLB. The Fargate cluster configuration is located in `mcp_server_deployer/src/lib/ecsFargateCluster.ts`.
* Authentication: API Gateway enforces the same Lambda authorizer used across LISA (JWT validation + optional API key checks). The `{LISA_BEARER_TOKEN}` placeholder in connection details is automatically replaced with the user's bearer token at connection time.
* Data Storage: Server metadata is stored in the `MCP_SERVERS_TABLE` DynamoDB table. When `DEPLOYMENT_PREFIX` is configured, completed servers are published to `McpConnectionsTable` so the chat application can surface them alongside externally hosted connections.

## Chat UI
![LISA Chatbot Architecture](../assets/LisaChat.png)

LISA provides a customizable chat user interface (UI). The UI is hosted as a static website in Amazon S3, and is fronted
by Amazon API Gateway. Customers prompt models and view real-time responses. The UI is integrated with LISA Serve, Chat
APIs, Model Management APIs, and RAG. LISA’s chat UI supports integration with an OIDC identity provider to handle user
authentication. LISA can be accessible to all users, or limited to a single enterprise user group. Users added to the
Administrator role have access to application configuration.

**LISA’s chat UI features include:**

* Prompting text and image generation LLMs and receiving responses
* Viewing, deleting, and exporting chat history
* Supports streaming responses, viewing metadata, and Markdown formatting
* Creating and sharing directive prompt and persona templates in a Prompt Library
* Advanced model args like max tokens, Top P, Temperature, stop words
* Referencing vector stores to support RAG
* Uploading docs into vector stores
* Uploading docs into non-RAG in context
* RAG document library
* Non-RAG in context Document summarization feature
* Model Context Protocol (MCP) support
* Administrators control which features are available without having to make code changes
* Administrators can configure models with LISA via the model manage wizard
* Administrators can add and manage vector stores and manage group access, and automatic ingestion pipelines
* Administrators can configure hosted MCP Servers via the MCP Management menu

## Model Management
![LISA Model Management Architecture](../assets/LisaModelManagement.png)

The Model Management is responsible for managing the entire lifecycle of models in LISA. This includes creation, updating,
deletion of models deployed on ECS or third party provided. LISA handles scaling of these operations, ensuring that the
underlying infrastructure is managed efficiently.

**Self-Hosted Models:** Models are containerized and deployed on AWS ECS. This design allows models to be independently
scaled based on demand. Traffic to the models is balanced using Application Load Balancers (ALBs), ensuring that the
autoscaling mechanism reacts to load fluctuations in real time, optimizing both performance and availability.

**External Model Routing:** LISA utilizes the LiteLLM proxy to route traffic to different model providers, no matter
their API and payload format. Administrators may configure models hosted by external providers, such as Amazon Bedrock,
to LISA. LISA will add the configuration to LiteLLM without creating any additional supporting infrastructure. Customers
do not have to independently manage each model’s unique API integration.

**Model Lifecycle Management:** AWS Step Functions are used to orchestrate the lifecycle of models, handling the creation,
update, and deletion workflows. Each workflow provisions the required resources using CloudFormation templates, which
manage infrastructure components like EC2 instances, security groups, and ECS services. LISA ensures that the necessary
security, networking, and infrastructure components are automatically deployed and configured.

* The CloudFormation stacks define essential resources using the LISA core VPC configuration, ensuring best practices for
  security and access across all resources in the environment.
* DynamoDB stores model metadata, while Amazon S3 securely manages model weights, enabling ECS instances to retrieve the
  weights dynamically during deployment.

**Technical Notes:**

* Model Lifecycle: Lifecycle operations such as creation, update, and deletion are executed by Step Functions and backed
  by AWS Lambda in `lambda/models/lambda_functions.py`.
* CloudFormation: Infrastructure components are provisioned using CloudFormation templates, as defined in
  `ecs_model_deployer/src/lib/lisa_model_stack.ts`.
* ECS Cluster: ECS cluster and task definitions are located in `ecs_model_deployer/src/lib/ecsCluster.ts`, with model
  containers specified in `ecs_model_deployer/src/lib/ecs-model.ts`.
