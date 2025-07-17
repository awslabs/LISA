
# Getting Started with LISA

LISA is an infrastructure-as-code solution that leverages AWS services. Customers deploy LISA directly into an AWS account.

## Deployment Prerequisites

### Pre-Deployment Steps

* Set up and have access to an AWS account with appropriate permissions
    * All the resource creation that happens as part of CDK deployments expects Administrator or Administrator-like permissions with resource creation and mutation permissions. Installation will not succeed if this profile does not have permissions to create and edit arbitrary resources for the system. Note: This level of permissions is not required for the runtime of LISA. This is only necessary for deployment and subsequent updates.
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

Create and configure your `config-custom.yaml` file:

```bash
cp example_config.yaml config-custom.yaml
```

Set the following environment variables:

```bash
export PROFILE=my-aws-profile  # Optional, can be left blank
export DEPLOYMENT_NAME=my-deployment
export ENV=dev  # Options: dev, test, or prod
export CDK_DOCKER=finch # Optional, only required if not using docker as container engine
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

Edit the `config-custom.yaml` file to customize your LISA deployment. Key configurations include:

- AWS account and region settings
- Authentication settings
- Model bucket name

## Step 5: Stage Model Weights

LISA requires model weights to be staged in the S3 bucket specified in your `config-custom.yaml` file, assuming the S3 bucket follows this structure:

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

To automatically download and stage the model weights defined by the `ecsModels` parameter in your `config-custom.yaml`, use the following command:

```bash
make modelCheck
```

This command verifies if the model's weights are already present in your S3 bucket. If not, it downloads the weights, converts them to the required format, and uploads them to your S3 bucket. Ensure adequate disk space is available for this process.

> **WARNING**
> As of LISA 3.0, the `ecsModels` parameter in `config-custom.yaml` is solely for staging model weights in your S3 bucket.
> Previously, before models could be managed through the [API](/config/model-management-api) or via the Model Management
> section of the [Chatbot](/user/chat), this parameter also
> dictated which models were deployed.

> **NOTE**
> For air-gapped systems, before running `make modelCheck` you should manually download model artifacts and place them in a `models` directory at the project root, using the structure: `models/<model-id>`.

> **NOTE**
> This process is primarily designed and tested for HuggingFace models. For other model formats, you will need to manually create and upload safetensors.

## Step 6: Configure Identity Provider

In the `config-custom.yaml` file, configure the `authConfig` block for authentication. LISA supports OpenID Connect (OIDC) providers such as AWS Cognito or Keycloak. Required fields include:

- `authority`: URL of your identity provider
- `clientId`: Client ID for your application
- `adminGroup`: Group name for users with model management permissions
- `userGroup`: Group name for regular LISA users
- `jwtGroupsProperty`: Path to the groups field in the JWT token
- `additionalScopes` (optional): Extra scopes for group membership information

IDP Configuration examples using AWS Cognito and Keycloak can be found: [IDP Configuration Examples](/admin/idp-config)


## Step 7: Configure LiteLLM
We utilize LiteLLM under the hood to allow LISA to respond to the [OpenAI specification](https://platform.openai.com/docs/api-reference).
For LiteLLM configuration, a key must be set up so that the system may communicate with a database for tracking all the models that are added or removed
using the [Model Management API](/config/model-management-api). The key must start with `sk-` and then can be any
arbitrary
string. We recommend generating a new UUID and then using that as
the key. Configuration example is below.


```yaml
litellmConfig:
  db_key: sk-00000000-0000-0000-0000-000000000000  # needed for db operations, create your own key # pragma: allowlist-secret
```

## Step 8: Set Up SSL Certificates (Development Only)

**WARNING: THIS IS FOR DEV ONLY**
When deploying for dev and testing you can use a self-signed certificate for the REST API ALB. You can create this by using the script: `gen-cert.sh` and uploading it to `IAM`.

```bash
export REGION=<your-region>
export DOMAIN=<your-domain> #Optional if not running in 'aws' partition
./scripts/gen-certs.sh
aws iam upload-server-certificate --server-certificate-name <cert-name> --certificate-body file://scripts/server.pem --private-key file://scripts/server.key
```

Update your `config-custom.yaml` with the certificate ARN:

```yaml
restApiConfig:
  sslCertIamArn: arn:<aws-partition>:iam::<account-number>:server-certificate/<certificate-name>
```

## Step 9: Customize Model Deployment

In the `ecsModels` section of `config-custom.yaml`, allow our deployment process to pull the model weights for you.

During the deployment process, LISA will optionally attempt to download your model weights if you specify an optional `ecsModels`
array, this will only work in non ADC regions. Specifically, see the `ecsModels` section of
the [example_config.yaml](https://github.com/awslabs/LISA/blob/develop/example_config.yaml) file.
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
Although there is support for it, we recommend using the [Model Management API](/config/model-management-api) instead of
the
following static configuration.
