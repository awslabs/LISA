
# Getting Started with LISA

LISA (LLM Inference Solution for Amazon Dedicated Cloud) is an advanced infrastructure solution for deploying and
managing Large Language Models (LLMs) on AWS. This guide will walk you through the setup process, from prerequisites
to deployment.

## Prerequisites

Before beginning, ensure you have:

1. An AWS account with appropriate permissions.
    1. Because of all the resource creation that happens as part of CDK deployments, we expect Administrator or Administrator-like permissions with resource creation and mutation permissions.
       Installation will not succeed if this profile does not have permissions to create and edit arbitrary resources for the system.
       **Note**: This level of permissions is not required for the runtime of LISA, only its deployment and subsequent updates.
2. AWS CLI installed and configured
3. Familiarity with AWS Cloud Development Kit (CDK) and infrastructure-as-code principles
4. Python 3.9 or later
5. Node.js 14 or later
6. Docker installed and running
7. Sufficient disk space for model downloads and conversions

If you're new to CDK, review the [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) and consult with your AWS support team.

> [!TIP]
> To minimize version conflicts and ensure a consistent deployment environment, it is recommended to execute the following steps on a dedicated EC2 instance. However, LISA can be deployed from any machine that meets the prerequisites listed above.

## Step 1: Clone the Repository

Ensure you're working with the latest stable release of LISA:

```bash
git clone -b main --single-branch <path-to-lisa-repo>
cd lisa
```

## Step 2: Set Up Environment Variables

Create and configure your `config.yaml` file:

```bash
cp example_config.yaml config.yaml
```

Set the following environment variables:

```bash
export PROFILE=my-aws-profile  # Optional, can be left blank
export DEPLOYMENT_NAME=my-deployment
export ENV=dev  # Options: dev, test, or prod
```

## Step 3: Set Up Python and TypeScript Environments

Install system dependencies and set up both Python and TypeScript environments:

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y jq

# Install Python packages
pip3 install --user --upgrade pip
pip3 install yq huggingface_hub s5cmd

# Set up Python environment
make createPythonEnvironment

# Activate your python environment
# The command is the output from the previous make command)

# Install Python Requirements
make installPythonRequirements

# Set up TypeScript environment
make createTypeScriptEnvironment
make installTypeScriptRequirements
```

## Step 4: Configure LISA

Edit the `config.yaml` file to customize your LISA deployment. Key configurations include:

- AWS account and region settings
- Model configurations
- Authentication settings
- Networking and infrastructure preferences

The full configuration page can be found: [Configuration](../ref/config)

## Step 5: Stage Model Weights

LISA requires model weights to be staged in the S3 bucket specified in your `config.yaml` file, assuming the S3 bucket follows this structure:

```
s3://<bucket-name>/<hf-model-id-1>
s3://<bucket-name>/<hf-model-id-1>/<file-1>
s3://<bucket-name>/<hf-model-id-1>/<file-2>
...
s3://<bucket-name>/<hf-model-id-2>
```

**Example:**

```
s3://<bucket-name>/mistralai/Mistral-7B-Instruct-v0.2
s3://<bucket-name>/mistralai/Mistral-7B-Instruct-v0.2/<file-1>
s3://<bucket-name>/mistralai/Mistral-7B-Instruct-v0.2/<file-2>
...
```

To automatically download and stage the model weights defined by the `ecsModels` parameter in your `config.yaml`, use the following command:

```bash
make modelCheck
```

This command verifies if the model's weights are already present in your S3 bucket. If not, it downloads the weights, converts them to the required format, and uploads them to your S3 bucket. Ensure adequate disk space is available for this process.

> **WARNING**
> As of LISA 3.0, the `ecsModels` parameter in `config.yaml` is solely for staging model weights in your S3 bucket. Previously, before models could be managed through the [API](https://github.com/awslabs/LISA/blob/develop/README.md#creating-a-model-admin-api) or via the Model Management section of the [Chatbot](https://github.com/awslabs/LISA/blob/develop/README.md#chatbot-example), this parameter also dictated which models were deployed.

> **NOTE**
> For air-gapped systems, before running `make modelCheck` you should manually download model artifacts and place them in a `models` directory at the project root, using the structure: `models/<model-id>`.

> **NOTE**
> This process is primarily designed and tested for HuggingFace models. For other model formats, you will need to manually create and upload safetensors.

## Step 6: Configure Identity Provider

In the `config.yaml` file, configure the `authConfig` block for authentication. LISA supports OpenID Connect (OIDC) providers such as AWS Cognito or Keycloak. Required fields include:

- `authority`: URL of your identity provider
- `clientId`: Client ID for your application
- `adminGroup`: Group name for users with model management permissions
- `jwtGroupsProperty`: Path to the groups field in the JWT token
- `additionalScopes` (optional): Extra scopes for group membership information

#### Cognito Configuration Example:
In Cognito, the `authority` will be the URL to your User Pool. As an example, if your User Pool ID, not the name, is `us-east-1_example`, and if it is
running in `us-east-1`, then the URL to put in the `authority` field would be `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example`. The `clientId`
can be found in your User Pool's "App integration" tab from within the AWS Management Console, and at the bottom of the page, you will see the list of clients
and their associated Client IDs. The ID here is what we will need for the `clientId` field.


```yaml
authConfig:
  authority: https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example
  clientId: your-client-id
  adminGroup: AdminGroup
  jwtGroupsProperty: cognito:groups
```

#### Keycloak Configuration Example:
In Keycloak, the `authority` will be the URL to your Keycloak server. The `clientId` is likely not a random string like in the Cognito clients, and instead
will be a string configured by your Keycloak administrator. Your administrator will be able to give you a client name or create a client for you to use for
this application. Once you have this string, use that as the `clientId` within the `authConfig` block.

```yaml
authConfig:
  authority: https://your-keycloak-server.com
  clientId: your-client-name
  adminGroup: AdminGroup
  jwtGroupsProperty: realm_access.roles
```

## Step 7: Configure LiteLLM
We utilize LiteLLM under the hood to allow LISA to respond to the [OpenAI specification](https://platform.openai.com/docs/api-reference).
For LiteLLM configuration, a key must be set up so that the system may communicate with a database for tracking all the models that are added or removed
using the [Model Management API](#admin-level-model-management-api). The key must start with `sk-` and then can be any arbitrary string. We recommend generating a new UUID and then using that as
the key. Configuration example is below.


```yaml
litellmConfig:
  general_settings:
    master_key: sk-00000000-0000-0000-0000-000000000000  # needed for db operations, create your own key # pragma: allowlist-secret
  model_list: []
```

**Note**: It is possible to add LiteLLM-only models to this configuration, but it is not recommended as the models in this configuration will not show in the
Chat or Model Management UIs. Instead, use the [Model Management UI](#admin-level-model-management-api) to add or remove LiteLLM-only model configurations.

## Step 8: Set Up SSL Certificates (Development Only)

**WARNING: THIS IS FOR DEV ONLY**
When deploying for dev and testing you can use a self-signed certificate for the REST API ALB. You can create this by using the script: `gen-cert.sh` and uploading it to `IAM`.

```bash
export REGION=<your-region>
./scripts/gen-certs.sh
aws iam upload-server-certificate --server-certificate-name <cert-name> --certificate-body file://scripts/server.pem --private-key file://scripts/server.key
```

Update your `config.yaml` with the certificate ARN:

```yaml
restApiConfig:
  loadBalancerConfig:
    sslCertIamArn: arn:aws:iam::<account-number>:server-certificate/<certificate-name>
```

## Step 9: Customize Model Deployment

In the `ecsModels` section of `config.yaml`, allow our deployment process to pull the model weights for you.

During the deployment process, LISA will optionally attempt to download your model weights if you specify an optional `ecsModels`
array, this will only work in non ADC regions. Specifically, see the `ecsModels` section of the [example_config.yaml](./example_config.yaml) file.
Here we define the model name, inference container, and baseImage:

```yaml
ecsModels:
  - modelName: your-model-name
    inferenceContainer: tgi
    baseImage: ghcr.io/huggingface/text-generation-inference:2.0.1
```

## Step 10: Bootstrap CDK (If Not Already Done)

If you haven't bootstrapped your AWS account for CDK:

```bash
make bootstrap
```

## Recommended LiteLLM Configuration Options

While LISA is designed to be flexible, configuring external models requires careful consideration. The following guide
provides a recommended minimal setup for integrating various model types with LISA using LiteLLM.

### Configuration Overview

This example configuration demonstrates how to set up:
1. A SageMaker Endpoint
2. An Amazon Bedrock Model
3. A self-hosted OpenAI-compatible text generation model
4. A self-hosted OpenAI-compatible embedding model

**Note:** Ensure that all endpoints and models are in the same AWS region as your LISA installation.

### SageMaker Endpoints and Bedrock Models

LISA supports adding existing SageMaker Endpoints and Bedrock Models to the LiteLLM configuration. As long as these
services are in the same region as the LISA installation, LISA can use them alongside any other deployed models.

**To use a SageMaker Endpoint:**
1. Install LISA without initially referencing the SageMaker Endpoint.
2. Create a SageMaker Model using the private subnets of the LISA deployment.
3. This setup allows the LISA REST API container to communicate with any Endpoint using that SageMaker Model.

**SageMaker Endpoints and Bedrock Models can be configured:**
- Statically at LISA deployment time
- Dynamically using the LISA Model Management API

**Important:** Endpoints or Models statically defined during LISA deployment cannot be removed or updated using the
LISA Model Management API, and they will not show in the Chat UI. These will only show as part of the OpenAI `/models` API.
Although there is support for it, we recommend using the [Model Management API](#admin-level-model-management-api) instead of the following static configuration.

### Example Configuration

```yaml
dev:
  litellmConfig:
    litellm_settings:
      telemetry: false  # Disable telemetry to LiteLLM servers (recommended for VPC deployments)
      drop_params: true # Ignore unrecognized parameters instead of failing

    model_list:
      # 1. SageMaker Endpoint Configuration
      - model_name: test-endpoint # Human-readable name, can be anything and will be used for OpenAI API calls
        litellm_params:
          model: sagemaker/test-endpoint # Prefix required for SageMaker Endpoints and "test-endpoint" matches Endpoint name
          api_key: ignored # Provide an ignorable placeholder key to avoid LiteLLM deployment failures
        lisa_params:
          model_type: textgen
          streaming: true

      # 2. Amazon Bedrock Model Configuration
      - model_name: bedrock-titan-express # Human-readable name for future OpenAI API calls
        litellm_params:
          model: bedrock/amazon.titan-text-express-v1 # Prefix required for Bedrock Models, and exact name of Model to use
          api_key: ignored # Provide an ignorable placeholder key to avoid LiteLLM deployment failures
        lisa_params:
          model_type: textgen
          streaming: true

      # 3. Custom OpenAI-compatible Text Generation Model
      - model_name: custom-openai-model # Used in future OpenAI-compatible calls to LiteLLM
        litellm_params:
          model: openai/custom-provider/textgen-model  # Format: openai/<provider>/<model-name>
          api_base: https://your-domain-here:443/v1 # Your model's base URI
          api_key: ignored # Provide an ignorable placeholder key to avoid LiteLLM deployment failures
        lisa_params:
          model_type: textgen
          streaming: true

      # 4. Custom OpenAI-compatible Embedding Model
      - model_name: custom-openai-embedding-model # Used in future OpenAI-compatible calls to LiteLLM
        litellm_params:
          model: openai/modelProvider/modelName # Prefix required for OpenAI-compatible models followed by model provider and name details
          api_base: https://your-domain-here:443/v1 # Your model's base URI
          api_key: ignored # Provide an ignorable placeholder key to avoid LiteLLM deployment failures
        lisa_params:
          model_type: embedding
```
