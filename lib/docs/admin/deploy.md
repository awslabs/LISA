# Deployment
## Prerequisites

* Set up or have access to an AWS account.
* Ensure that your AWS account has the appropriate permissions. Resource creation during the AWS CDK deployment expects Administrator or Administrator-like permissions, to include resource creation and mutation permissions. Installation will not succeed if this profile does not have permissions to create and edit arbitrary resources for the system. This level of permissions is not required for the runtime of LISA. This is only necessary for deployment and subsequent updates.
* If using the chat UI, have your Identity Provider (IdP) information available, and access.
* If using an existing VPC, have its information available.
* Familiarity with AWS Cloud Development Kit (CDK) and infrastructure-as-code principles is a plus.
* AWS CDK and Model Management both leverage AWS Systems Manager Agent (SSM) parameter store. Confirm that SSM is approved for use by your organization before beginning. If you're new to CDK, review the [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) and consult with your AWS support team.

## Software

* AWS CLI installed and configured
* Python 3.11
* Node.js 20
* Docker installed and running
* Sufficient disk space for model downloads and conversions

> **TIP:**
>
> To minimize version conflicts and ensure a consistent deployment environment, we recommend executing the following steps on a dedicated EC2 instance. However, LISA can be deployed from any machine that meets the prerequisites listed above.

## Deployment Steps
### Step 1: Clone the Repository

Ensure you're working with the latest stable release of LISA:

```bash
git clone -b main --single-branch <path-to-lisa-repo>
cd lisa
```

### Step 2: Set Up Environment Variables

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

### Step 3: Set Up Python and TypeScript Environments

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

### Step 4: Configure LISA

Edit the `config-custom.yaml` file to customize your LISA deployment. Key configurations include:

- AWS account and region settings
- Authentication settings
- Model bucket name

### Step 5: Stage Model Weights

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

### Step 6: Configure Identity Provider

In the `config-custom.yaml` file, configure the `authConfig` block for authentication. LISA supports OpenID Connect (OIDC) providers such as AWS Cognito or Keycloak. Required fields include:

- `authority`: URL of your identity provider
- `clientId`: Client ID for your application
- `adminGroup`: Group name for users with model management permissions
- `userGroup`: Group name for regular LISA users
- `jwtGroupsProperty`: Path to the groups field in the JWT token
- `additionalScopes` (optional): Extra scopes for group membership information

IDP Configuration examples using AWS Cognito and Keycloak can be found: [IDP Configuration Examples](/admin/idp-config)


### Step 7: Configure LiteLLM
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

### Step 8: Set Up SSL Certificates (Development Only)

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

### Step 9: Customize Model Deployment

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

### Step 10: Bootstrap CDK (If Not Already Done)

If you haven't bootstrapped your AWS account for CDK:

```bash
make bootstrap
```
## ADC Region Deployment Tips

Amazon Dedicated Cloud (ADC) regions are isolated AWS environments designed for government customers' most sensitive workloads. These regions have restricted internet access and limited external dependencies, requiring special deployment considerations for LISA.

There are two deployment approaches for ADC regions:

1. **Pre-built Resources (Recommended)**: Build all components in a commercial region, then transfer to ADC
2. **In-Region Building**: Configure LISA to use ADC-accessible repositories for building components

### Approach 1: Pre-built Resources (Recommended)

This approach builds all necessary components in a commercial region with full internet access, then transfers them to the ADC region.

#### Step 1: Build Components in Commercial Region

1. Set up LISA in a commercial AWS region with internet access
2. Build all components:
   ```bash
   make buildArchive
   ```
   This generates:
   - Lambda function zip files in `./dist/layers/*.zip`
   - Docker images exported as `./dist/images/*.tar` files

#### Step 2: Transfer to ADC Region

1. Upload Docker images to ECR in your ADC region:
   ```bash
   # Load and tag images
   docker load -i lisa-rest-api.tar
   docker tag lisa-rest-api:latest <adc-account-id>.dkr.ecr.<adc-region>.amazonaws.com/lisa-rest-api:latest

   # Push to ADC ECR
   aws ecr get-login-password --region <adc-region> | docker login --username AWS --password-stdin <adc-account-id>.dkr.ecr.<adc-region>.amazonaws.com
   docker push <adc-account-id>.dkr.ecr.<adc-region>.amazonaws.com/lisa-rest-api:latest
   ```
   You'll want to repeat this for lisa-batch-ingestion, as well as any of the LISA base model hosting containers (lisa-vllm, lisa-tgi, lisa-tei)

2. Transfer built artifacts to ADC environment

#### Step 3: Configure LISA for Pre-built Resources

Update your `config-custom.yaml` in the ADC region:

```yaml
# Lambda layers from pre-built archives
lambdaLayerAssets:
  authorizerLayerPath: './dist/layers/AimlAdcLisaAuthLayer.zip'
  commonLayerPath: './dist/layers/AimlAdcLisaCommonLayer.zip'
  fastapiLayerPath: './dist/layers/AimlAdcLisaFastApiLayer.zip'
  ragLayerPath: './dist/layers/AimlAdcLisaRag.zip'
  sdkLayerPath: './dist/layers/AimlAdcLisaSdk.zip'

# Lambda functions
lambdaPath: './dist/layers/AimlAdcLisaLambda.zip'

# Pre-built web assets
webAppAssetsPath: './dist/lisa-web'
documentsPath: './dist/docs'
ecsModelDeployerPath: './dist/ecs_model_deployer'
vectorStoreDeployerPath: './dist/vector_store_deployer'

# Container images from ECR
batchIngestionConfig:
  type: external
  code: <adc-account-id>.dkr.ecr.<adc-region>.amazonaws.com/lisa-batch-ingestion:latest

restApiConfig:
  imageConfig:
    type: external
    code: <adc-account-id>.dkr.ecr.<adc-region>.amazonaws.com/lisa-rest-api:latest
```



### Approach 2: In-Region Building

This approach configures LISA to build components using repositories accessible from within the ADC region.

#### Prerequisites
- ADC-accessible package repositories (PyPI mirror, npm registry, container registry)
- ADC-accessible container registries
- Network connectivity to required build dependencies

#### Configuration

Update your `config-custom.yaml` to point to ADC-accessible repositories:

```yaml
# Configure pip to use ADC-accessible PyPI mirror
pypiConfig:
  indexUrl: https://your-adc-pypi-mirror.com/simple
  trustedHost: your-adc-pypi-mirror.com

# Configure npm to use ADC-accessible registry
npmConfig:
  registry: https://your-adc-npm-registry.com

# Use ADC-accessible base images for LISA-Serve and Batch Ingestion
baseImage: <adc-registry>/python:3.11

# Configure offline build dependencies for REST API (prisma-client-py dependencies)
restApiConfig:
  buildConfig:
    PRISMA_CACHE_DIR: "./PRISMA_CACHE"  # Path relative to lib/serve/rest-api/

# Configure offline build dependencies for MCP Workbench (S6 Overlay and rclone)
mcpWorkbenchBuildConfig:
  S6_OVERLAY_NOARCH_SOURCE: "./s6-overlay-noarch.tar.xz"  # Path relative to lib/serve/mcp-workbench/
  S6_OVERLAY_ARCH_SOURCE: "./s6-overlay-x86_64.tar.xz"    # Path relative to lib/serve/mcp-workbench/
  RCLONE_SOURCE: "./rclone-linux-amd64.zip"                # Path relative to lib/serve/mcp-workbench/
```
You'll also want any model hosting base containers available, e.g. vllm/vllm-openai:latest and ghcr.io/huggingface/text-embeddings-inference:latest

#### Preparing Offline Build Dependencies

For environments without internet access during Docker builds, you can pre-cache required dependencies:

**REST API Prisma cache** (required by prisma-client-py):

The `prisma-client-py` package requires platform-specific binaries and a Node.js environment to function. When Prisma runs for the first time, it downloads these dependencies to `~/.cache/prisma/` and `~/.cache/prisma-python/`. For offline deployments, you need to pre-populate this cache.

Below is an example workflow using an Amazon Linux 2023 instance with Python 3.12:

```bash
# Ensure Pip is up-to-date
pip3 install --upgrade pip

# Install Prisma Python package
pip3 install prisma

# Trigger Prisma to download all required binaries and create its Node.js environment
# This populates ~/.cache/prisma/ and ~/.cache/prisma-python/
prisma version

# Copy the complete Prisma cache to your build context
# The wildcard captures both 'prisma' and 'prisma-python' directories
cp -r ~/.cache/prisma* lib/serve/rest-api/PRISMA_CACHE/
```

**Important Notes:**
- The cache is platform-specific. Generate it on a system matching your Docker base image (e.g., Amazon Linux 2023 for `python:3.13-slim` which is Debian-based, so you may want to use a Debian-based system)
- The `prisma version` command downloads binaries for your current platform
- Both `prisma/` and `prisma-python/` directories are required for offline operation

**MCP Workbench dependencies** (S6 Overlay and rclone):
```bash
# Download S6 Overlay files
cd lib/serve/mcp-workbench/
wget https://github.com/just-containers/s6-overlay/releases/download/v3.1.6.2/s6-overlay-noarch.tar.xz
wget https://github.com/just-containers/s6-overlay/releases/download/v3.1.6.2/s6-overlay-x86_64.tar.xz

# Download rclone
wget https://github.com/rclone/rclone/releases/download/v1.71.0/rclone-v1.71.0-linux-amd64.zip

cd ../../..
```

These cached dependencies will be used during the Docker build process instead of downloading from the internet.

To utilize the prebuilt hosting model containers with self-hosted models, select `type: ecr` in the Model Deployment > Container Configs.

### Deployment Steps

Once your configuration is complete:

1. Bootstrap CDK (if not already done):
   ```bash
   make bootstrap
   ```

2. Deploy LISA:
   ```bash
   make deploy
   ```

3. Deploy specific stacks if needed:
   ```bash
   make deploy STACK=LisaServe
   ```

4. List available stacks:
   ```bash
   make listStacks
   ```

### Testing Your Deployment

After deployment completes (10-15 minutes), test with:

```bash
pytest lisa-sdk/tests --url <rest-url-from-cdk-output> --verify <path-to-server.crt>
```

### Troubleshooting ADC Deployments

- **Build failures**: Ensure all dependencies are accessible from ADC region
- **Container pull errors**: Verify ECR repositories exist and have correct permissions
- **Lambda deployment issues**: Check that lambda zip files are properly formatted and accessible
- **Network connectivity**: Confirm VPC configuration allows required outbound connections
