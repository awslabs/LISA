# Configuration Generator CLI

The Configuration Generator is an interactive command-line tool that helps you create a valid `config-custom.yaml` file for LISA deployment. Instead of manually editing YAML files, the generator prompts you for each configuration value, validates your inputs, and produces a properly formatted configuration file.

## Running the Generator

From the project root, run:

```bash
npm run generate-config
```

Or directly with tsx:

```bash
npx tsx scripts/generate-config.ts
```

## What It Configures

The generator walks you through the following configuration sections:

### Core Configuration

- **AWS Account Number**: Your 12-digit AWS account ID
- **AWS Region**: The region for deployment (e.g., `us-east-1`)
- **AWS Partition**: The AWS partition (`aws`, `aws-cn`, `aws-gov`, `aws-iso`, `aws-iso-b`, `aws-iso-f`)
- **Deployment Stage**: Environment identifier (default: `prod`)
- **Deployment Name**: Name for your deployment (default: `prod`)
- **S3 Bucket for Models**: The S3 bucket where your models are stored

### Prebuilt Assets

If you're using prebuilt assets from `@amzn/lisa-adc`, the generator automatically configures:

- Lambda layer paths
- Web app assets path
- Documentation path
- ECS model deployer path
- Vector store deployer path
- ECR image configurations for REST API, MCP Workbench, and Batch Ingestion

### Authentication (Optional)

- **OIDC Authority URL**: Your identity provider's authority URL
- **Client ID**: The OIDC client ID
- **Admin Group**: Group name for admin users
- **JWT Groups Property**: The JWT claim containing user groups

### API Gateway (Optional)

- **Domain Name**: Custom domain for API Gateway

### REST API (Optional)

- **SSL Certificate IAM ARN**: ARN of your SSL certificate
- **Domain Name**: Custom domain for the REST API

### ECS Models (Optional)

Configure models to deploy on ECS:

- **Model Name**: The S3 path where the model is stored (e.g., `openai/gpt-oss-20b`)
- **Inference Container**: The container type (`vllm`, `tei`, or `tgi`)
- **Base Image**: The container image (defaults provided for each container type)

### Feature Flags

Enable or disable LISA features:

- Deploy Chat
- Deploy Metrics
- Deploy MCP Workbench
- Deploy RAG
- Deploy Docs
- Deploy UI
- Deploy MCP
- Deploy Serve

## File Handling

The generator handles existing configuration files gracefully:

- **No existing config**: Creates `config-custom.yaml`
- **Existing config found**: Offers to merge with existing values or create a new `config-generated.yaml`

When merging, your existing values are preserved and new values are added or updated.

## Example Session

```
╔════════════════════════════════════════════════════════════════╗
║           LISA Configuration Generator                         ║
║   Generate a config-custom.yaml for LISA deployment            ║
╚════════════════════════════════════════════════════════════════╝

📋 Core Configuration

AWS Account Number (12 digits): 123456789012
AWS Region: us-east-1

Partition options: aws, aws-cn, aws-gov, aws-iso, aws-iso-b, aws-iso-f
AWS Partition [aws]: aws
Deployment Stage [prod]: prod
Deployment Name [prod]: prod
S3 Bucket for Models: my-models-bucket

📦 Prebuilt Assets

Use prebuilt assets from @amzn/lisa-adc? [Y/n]: y

🔐 Authentication Configuration

Configure Authentication? [y/N]: y
OIDC Authority URL: https://cognito-idp.us-east-1.amazonaws.com/us-east-1_xxxxx
Client ID: my-client-id
Admin Group Name (optional): admins
JWT Groups Property (optional): cognito:groups

🤖 ECS Model Configuration

Models will be deployed from S3 bucket: my-models-bucket
The model name corresponds to the path in S3 where the model is stored.
Example: "openai/gpt-oss-20b" means s3://my-models-bucket/openai/gpt-oss-20b

Would you like to add ECS models? [y/N]: y

--- Model 1 ---
Model name (S3 path, e.g., openai/gpt-oss-20b): openai/gpt-oss-20b

Inference container options: vllm, tei, tgi
Inference container type [vllm]: vllm
Base image [vllm/vllm-openai:latest]: vllm/vllm-openai:latest

✓ Added model: openai/gpt-oss-20b (vllm)

Add another model? [y/N]: n

🚀 Feature Deployment Flags

Use default feature flags (all enabled)? [Y/n]: y

✅ Configuration generated successfully!
📄 Output file: config-custom.yaml
```

## Example Output

```yaml
accountNumber: "123456789012"
region: us-east-1
partition: aws
deploymentStage: prod
deploymentName: prod
s3BucketModels: my-models-bucket
ragRepositories: []
ecsModels:
  - modelName: openai/gpt-oss-20b
    baseImage: vllm/vllm-openai:latest
    inferenceContainer: vllm
authConfig:
  authority: https://cognito-idp.us-east-1.amazonaws.com/us-east-1_xxxxx
  clientId: my-client-id
  adminGroup: admins
  jwtGroupsProperty: cognito:groups
restApiConfig:
  imageConfig:
    type: ecr
    repositoryArn: arn:aws:ecr:us-east-1:123456789012:repository/lisa-rest-api
    tag: latest
mcpWorkbenchConfig:
  imageConfig:
    type: ecr
    repositoryArn: arn:aws:ecr:us-east-1:123456789012:repository/lisa-mcp-workbench
    tag: latest
batchIngestionConfig:
  imageConfig:
    type: ecr
    repositoryArn: arn:aws:ecr:us-east-1:123456789012:repository/lisa-batch-ingestion
    tag: latest
lambdaLayerAssets:
  authorizerLayerPath: ./node_modules/@amzn/lisa-adc/dist/layers/AimlAdcLisaAuthLayer.zip
  commonLayerPath: ./node_modules/@amzn/lisa-adc/dist/layers/AimlAdcLisaCommonLayer.zip
  fastapiLayerPath: ./node_modules/@amzn/lisa-adc/dist/layers/AimlAdcLisaFastApiLayer.zip
  ragLayerPath: ./node_modules/@amzn/lisa-adc/dist/layers/AimlAdcLisaRag.zip
  sdkLayerPath: ./node_modules/@amzn/lisa-adc/dist/layers/AimlAdcLisaSdk.zip
deployChat: true
deployMetrics: true
deployMcpWorkbench: true
deployRag: true
deployDocs: true
deployUi: true
deployMcp: true
deployServe: true
```

## Validation

The generator validates all inputs:

- **Account Number**: Must be exactly 12 digits
- **Region**: Must be a valid AWS region
- **Partition**: Must be one of the supported AWS partitions
- **Inference Container**: Must be `vllm`, `tei`, or `tgi`
- **Required Fields**: Cannot be empty

Invalid inputs display an error message and re-prompt for the correct value.
