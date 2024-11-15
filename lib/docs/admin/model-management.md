
# Model Management API Usage

LISA provides robust API endpoints for managing models, both for users and administrators. These endpoints allow for operations such as listing, creating, updating, and deleting models.

## API Gateway and ALB Endpoints

LISA uses two primary APIs for model management:

1. **User-facing OpenAI-Compatible API**: Available to all users for inference tasks and accessible through the LISA Serve ALB. This API provides an interface for querying and interacting with models deployed on Amazon ECS, Amazon Bedrock, or through LiteLLM.
2. **Admin-level Model Management API**: Available only to administrators through the API Gateway (APIGW). This API allows for full control of model lifecycle management, including creating, updating, and deleting models.

### LiteLLM Routing in All Models

Every model request is routed through LiteLLM, regardless of whether infrastructure (like ECS) is created for it. Whether deployed on ECS, external models via Bedrock, or managed through LiteLLM, all models are added to LiteLLM for traffic routing. The distinction is whether infrastructure is created (determined by request payloads), but LiteLLM integration is consistent for all models. The model management APIs will handle adding or removing model configurations from LiteLLM, and the LISA Serve endpoint will handle the inference requests against models available in LiteLLM.

## User-facing OpenAI-Compatible API

The OpenAI-compatible API is accessible through the LISA Serve ALB and allows users to list models available for inference tasks. Although not specifically part of the model management APIs, any model that is added or removed from LiteLLM via the model management API Gateway APIs will be reflected immediately upon queries to LiteLLM through the LISA Serve ALB.

### Listing Models

The `/v2/serve/models` endpoint on the LISA Serve ALB allows users to list all models available for inference in the LISA system.

#### Request Example:

```bash
curl -s -H 'Authorization: Bearer <your_token>' -X GET https://<alb_endpoint>/v2/serve/models
```

#### Response Example:

```json
{
  "data": [
    {
      "id": "bedrock-embed-text-v2",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai"
    },
    {
      "id": "titan-express-v1",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai"
    },
    {
      "id": "sagemaker-amazon-mistrallite",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai"
    }
  ],
  "object": "list"
}
```

#### Explanation of Response Fields:

These fields are all defined by the OpenAI API specification, which is documented [here](https://platform.openai.com/docs/api-reference/models/list).

- `id`: A unique identifier for the model.
- `object`: The type of object, which is "model" in this case.
- `created`: A Unix timestamp representing when the model was created.
- `owned_by`: The entity responsible for the model, such as "openai."

## Admin-level Model Management API

This API is only accessible by administrators via the API Gateway and is used to create, update, and delete models. It supports full model lifecycle management.

### Listing Models (Admin API)

The `/models` route allows admins to list all models managed by the system. This includes models that are either creating, deleting, already active, or in a failed state. Models can be deployed via ECS or managed externally through a LiteLLM configuration.

#### Request Example:

```bash
curl -s -H "Authorization: Bearer <admin_token>" -X GET https://<apigw_endpoint>/models
```

#### Response Example:

```json
{
  "models": [
    {
      "autoScalingConfig": {
        "minCapacity": 1,
        "maxCapacity": 1,
        "cooldown": 420,
        "defaultInstanceWarmup": 180,
        "metricConfig": {
          "albMetricName": "RequestCountPerTarget",
          "targetValue": 30,
          "duration": 60,
          "estimatedInstanceWarmup": 330
        }
      },
      "containerConfig": {
        "image": {
          "baseImage": "vllm/vllm-openai:v0.5.0",
          "type": "asset"
        },
        "sharedMemorySize": 2048,
        "healthCheckConfig": {
          "command": [
            "CMD-SHELL",
            "exit 0"
          ],
          "interval": 10,
          "startPeriod": 30,
          "timeout": 5,
          "retries": 3
        },
        "environment": {
          "MAX_TOTAL_TOKENS": "2048",
          "MAX_CONCURRENT_REQUESTS": "128",
          "MAX_INPUT_LENGTH": "1024"
        }
      },
      "loadBalancerConfig": {
        "healthCheckConfig": {
          "path": "/health",
          "interval": 60,
          "timeout": 30,
          "healthyThresholdCount": 2,
          "unhealthyThresholdCount": 10
        }
      },
      "instanceType": "g5.xlarge",
      "modelId": "mistral-vllm",
      "modelName": "mistralai/Mistral-7B-Instruct-v0.2",
      "modelType": "textgen",
      "modelUrl": null,
      "status": "Creating",
      "streaming": true
    },
    {
      "autoScalingConfig": null,
      "containerConfig": null,
      "loadBalancerConfig": null,
      "instanceType": null,
      "modelId": "titan-express-v1",
      "modelName": "bedrock/amazon.titan-text-express-v1",
      "modelType": "textgen",
      "modelUrl": null,
      "status": "InService",
      "streaming": true
    }
  ]
}
```

#### Explanation of Response Fields:

- `modelId`: A unique identifier for the model.
- `modelName`: The name of the model, typically referencing the underlying service (Bedrock, SageMaker, etc.).
- `status`: The current state of the model, e.g., "Creating," "Active," or "Failed."
- `streaming`: Whether the model supports streaming inference.
- `instanceType` (optional): The instance type if the model is deployed via ECS.

### Creating a Model (Admin API)

LISA provides the `/models` endpoint for creating both ECS and LiteLLM-hosted models. Depending on the request payload, infrastructure will be created or bypassed (e.g., for LiteLLM-only models).

This API accepts the same model definition parameters that were accepted in the V2 model definitions within the config.yaml file with one notable difference: the `containerConfig.image.path` field is
now omitted because it corresponded with the `inferenceContainer` selection. As a convenience, this path is no longer required.

#### Request Example:

```
POST https://<apigw_endpoint>/models
```

#### Example Payload for ECS Model:

```json
{
  "modelId": "mistral-vllm",
  "modelName": "mistralai/Mistral-7B-Instruct-v0.2",
  "modelType": "textgen",
  "inferenceContainer": "vllm",
  "instanceType": "g5.xlarge",
  "streaming": true,
  "containerConfig": {
    "image": {
      "baseImage": "vllm/vllm-openai:v0.5.0",
      "type": "asset"
    },
    "sharedMemorySize": 2048,
    "environment": {
      "MAX_CONCURRENT_REQUESTS": "128",
      "MAX_INPUT_LENGTH": "1024",
      "MAX_TOTAL_TOKENS": "2048"
    },
    "healthCheckConfig": {
      "command": ["CMD-SHELL", "exit 0"],
      "interval": 10,
      "startPeriod": 30,
      "timeout": 5,
      "retries": 3
    }
  },
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 1,
    "cooldown": 420,
    "defaultInstanceWarmup": 180,
    "metricConfig": {
      "albMetricName": "RequestCountPerTarget",
      "targetValue": 30,
      "duration": 60,
      "estimatedInstanceWarmup": 330
    }
  },
  "loadBalancerConfig": {
    "healthCheckConfig": {
      "path": "/health",
      "interval": 60,
      "timeout": 30,
      "healthyThresholdCount": 2,
      "unhealthyThresholdCount": 10
    }
  }
}
```

#### Creating a LiteLLM-Only Model:

```json
{
  "modelId": "titan-express-v1",
  "modelName": "bedrock/amazon.titan-text-express-v1",
  "modelType": "textgen",
  "streaming": true
}
```

#### Explanation of Key Fields for Creation Payload:

- `modelId`: The unique identifier for the model. This is any name you would like it to be.
- `modelName`: The name of the model as it appears in the system. For LISA-hosted models, this must be the S3 Key to your model artifacts, otherwise
  this is the LiteLLM-compatible reference to a SageMaker Endpoint or Bedrock Foundation Model. Note: Bedrock and SageMaker resources must exist in the
  same region as your LISA deployment. If your LISA installation is in us-east-1, then all SageMaker and Bedrock calls will also happen in us-east-1.
  Configuration examples:
    - LISA hosting: If your model artifacts are in `s3://${lisa_models_bucket}/path/to/model/weights`, then the `modelName` value here should be `path/to/model/weights`
    - LiteLLM-only, Bedrock: If you want to use `amazon.titan-text-lite-v1`, your `modelName` value should be `bedrock/amazon.titan-text-lite-v1`
    - LiteLLM-only, SageMaker: If you want to use a SageMaker Endpoint named `my-sm-endpoint`, then the `modelName` value should be `sagemaker/my-sm-endpoint`.
- `modelType`: The type of model, such as text generation (textgen).
- `streaming`: Whether the model supports streaming inference.
- `instanceType`: The type of EC2 instance to be used (only applicable for ECS models).
- `containerConfig`: Details about the Docker container, memory allocation, and environment variables.
- `autoScalingConfig`: Configuration related to ECS autoscaling.
- `loadBalancerConfig`: Health check configuration for load balancers.

### Deleting a Model (Admin API)

Admins can delete a model using the following endpoint. Deleting a model removes the infrastructure (ECS) or disconnects from LiteLLM.

#### Request Example:

```
DELETE https://<apigw_endpoint>/models/{modelId}
```

#### Response Example:

```json
{
  "status": "success",
  "message": "Model mistral-vllm has been deleted successfully."
}
```

### Updating a Model

LISA offers basic updating functionality for both LISA-hosted and LiteLLM-only models. For both types, the model type and streaming support can be updated
in the cases that the models were originally created with the wrong parameters. For example, if an embedding model was accidentally created as a `textgen`
model, the UpdateModel API can be used to set it to the intended `embedding` value. Additionally, for LISA-hosted models, users may update the AutoScaling
configuration to increase or decrease capacity usage for each model. Users may use this API to completely shut down all instances behind a model until
they want to add capacity back to the model for usage later. This feature can help users to effectively manage costs so that instances do not have to stay
running in time periods of little or no expected usage.

The UpdateModel API has mutually exclusive payload fields to avoid conflicting requests. The API does not allow for shutting off a model at the same time
as updating its AutoScaling configuration, as these would introduce ambiguous intents. The API does not allow for setting AutoScaling limits to 0 and instead
requires the usage of the enable/disable functionality to allow models to fully scale down or turn back on. Metadata updates, such as changing the model type
or streaming compatibility, can happen in either type of update or simply by themselves.

#### Request Example

```
PUT https://<apigw_endpoint>/models/{modelId}
```

#### Example Payloads

##### Update Model Metadata

This payload will simply update the model metadata, which will complete within seconds of invoking. If setting a model as an `embedding` model, then the
`streaming` option must be set to `false` or omitted as LISA does not support streaming with embedding models. Both the `streaming` and `modelType` options
may be included in any other update request.

```json
{
  "streaming": true,
  "modelType": "textgen"
}
```

##### Update AutoScaling Configuration

This payload will update the AutoScaling configuration for minimum, maximum, and desired number of instances. The desired number must be between the
minimum or maximum numbers, inclusive, and all the numbers must be strictly greater than 0. If the model currently has less than the minimum number, then
the desired count will automatically raise to the minimum if a desired count is not specified. Despite setting a desired capacity, the model will scale down
to the minimum number over time if you are not hitting the scaling thresholds set when creating the model in the first place.

The AutoScaling configuration **can** be updated while the model is in the Stopped state, but it won't be applied immediately. Instead, the configuration will
be saved until the model is started again, in which it will use the most recently updated AutoScaling configuration.

The request will fail if the `autoScalingInstanceConfig` is defined at the same time as the `enabled` field. These options are mutually exclusive and must be
handled as separate operations. Any or all of the options within the `autoScalingInstanceConfig` may be set as needed, so if you only wish to change the `desiredCapacity`,
then that is the only option that you need to specify in the request object within the `autoScalingInstanceConfig`.

```json
{
  "autoScalingInstanceConfig": {
    "minCapacity": 2,
    "maxCapacity": 4,
    "desiredCapacity": 3
  }
}
```

##### Stop Model - Scale Down to 0 Instances

This payload will stop all model EC2 instances and remove the model reference from LiteLLM so that users are unable to make inference requests against a model
with no capacity. This option is useful for users who wish to manage costs and turn off instances when the model is not currently needed but will be used again
in the future.

The request will fail if the `enabled` field is defined at the same time as the `autoScalingInstanceConfig` field. These options are mutually exclusive and must be
handled as separate operations.

```json
{
  "enabled": false
}
```

##### Start Model - Restore Previous AutoScaling Configuration

After stopping a model, this payload will turn the model back on by spinning up instances, waiting for the expected spin-up time to allow models to initialize, and then
adding the reference back to LiteLLM so that users may query the model again. This is expected to be a much faster operation than creating the model through the CreateModel
API, so as long as the model details don't have to change, this in combination with the Stop payload will help to manage costs while still providing model availability as
quickly as the system can spin it up again.

The request will fail if the `enabled` field is defined at the same time as the `autoScalingInstanceConfig` field. These options are mutually exclusive and must be
handled as separate operations.

```json
{
  "enabled": true
}
```
