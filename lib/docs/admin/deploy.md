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
* Python 3.9 or later
* Node.js 14 or later
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

If you are deploying LISA into an ADC region with limited access to dependencies, we recommend that you build LISA in a
commercial region first, and then bring it up into your ADC region to deploy. First, do the npm and pip installs on a
computer with access to the dependencies. Then bundle it up with the libraries included and move into the ADC region.
Some properties will need to be set in the deployment file pointing to the built artifacts. From there the deployment
process is the same.

### Using pre-built resources

A default configuration will build the necessary containers, lambda layers, and production optimized
web application at build time. In the event that you would like to use pre-built resources due to
network connectivity reasons or other concerns with the environment where you'll be deploying LISA
you can do so.

- For ECS containers (Models, APIs, etc) you can modify the `containerConfig` block of
  the corresponding entry in `config.yaml`. For container images you can provide a path to a directory
  from which a docker container will be built (default), a path to a tarball, an ECR repository arn and
  optional tag, or a public registry path.
    - We provide immediate support for HuggingFace TGI and TEI containers and for vLLM containers. The `example_config.yaml`
      file provides examples for TGI and TEI, and the only difference for using vLLM is to change the
      `inferenceContainer`, `baseImage`, and `path` options, as indicated in the snippet below. All other options can
      remain the same as the model definition examples we have for the TGI or TEI models. vLLM can also support embedding
      models in this way, so all you need to do is refer to the embedding model artifacts and remove the `streaming` field
      to deploy the embedding model.
    - vLLM has support for the OpenAI Embeddings API, but model support for it is limited because the feature is new. Currently,
      the only supported embedding model with vLLM is [intfloat/e5-mistral-7b-instruct](https://huggingface.co/intfloat/e5-mistral-7b-instruct),
      but this list is expected to grow over time as vLLM updates.
      ```yaml
      ecsModels:
        - modelName: your-model-name
          inferenceContainer: tgi
          baseImage: ghcr.io/huggingface/text-generation-inference:2.0.1
      ```
- If you are deploying the LISA Chat User Interface you can optionally specify the path to the pre-built
  website assets using the top level `webAppAssetsPath` parameter in `config.yaml`. Specifying this path
  (typically `lib/user-interface/react/dist`) will avoid using a container to build and bundle the assets
  at CDK build time.
- For the lambda layers you can specify the path to a local zip archive of the layer code by including
  the optional `lambdaLayerAssets` block in `config.yaml` similar to the following:

```
lambdaLayerAssets:
  authorizerLayerPath: lib/core/layers/authorizer_layer.zip
  commonLayerPath: lib/core/layers/common_layer.zip
  fastapiLayerPath: /path/to/fastapi_layer.zip
  sdkLayerPath: lib/rag/layers/sdk_layer.zip
```

### Deploying in ADC region

Now that we have everything setup we are ready to deploy.

```bash
make deploy
```

By default, all stacks will be deployed but a particular stack can be deployed by providing the `STACK` argument to the `deploy` target.

```bash
make deploy STACK=LisaServe
```

Available stacks can be listed by running:

```bash
make listStacks
```

After the `deploy` command is run, you should see many docker build outputs and eventually a CDK progress bar. The deployment should take about 10-15 minutes and will produce a single cloud formation output for the websocket URL.

You can test the deployment with the integration test:

```bash
pytest lisa-sdk/tests --url <rest-url-from-cdk-output> --verify <path-to-server.crt> | false
```
