# Admin-level Model Management API

This API is only accessible by administrators via the API Gateway and is used to create, update, and delete models. It supports full model lifecycle management.

## Listing Models (Admin API)

The `/models` route allows admins to list all models managed by the system. This includes models that are either creating, deleting, already active, or in a failed state. Models can be deployed via ECS or managed externally through a LiteLLM configuration.

### Request Example:

```bash
curl -s -H "Authorization: Bearer <admin_token>" -X GET https://<apigw_endpoint>/models
```

### Response Example:

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

### Explanation of Response Fields:

- `modelId`: A unique identifier for the model.
- `modelName`: The name of the model, typically referencing the underlying service (Bedrock, SageMaker, etc.).
- `status`: The current state of the model, e.g., "Creating," "Active," or "Failed."
- `streaming`: Whether the model supports streaming inference.
- `instanceType` (optional): The instance type if the model is deployed via ECS.

## Creating a Model (Admin API)

LISA provides the `/models` endpoint for creating both ECS and LiteLLM-hosted models. Depending on the request payload, infrastructure will be created or bypassed (e.g., for LiteLLM-only models).

This API accepts the same model definition parameters that were accepted in the V2 model definitions within the config.yaml file with one notable difference: the `containerConfig.image.path` field is
now omitted because it corresponded with the `inferenceContainer` selection. As a convenience, this path is no longer required.

### Request Example:

```
POST https://<apigw_endpoint>/models
```

### Example Payload for ECS Model:

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

### Creating a LiteLLM-Only Model:

```json
{
  "modelId": "titan-express-v1",
  "modelName": "bedrock/amazon.titan-text-express-v1",
  "modelType": "textgen",
  "streaming": true
}
```

### Explanation of Key Fields for Creation Payload:

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

## Deleting a Model (Admin API)

Admins can delete a model using the following endpoint. Deleting a model removes the infrastructure (ECS) or disconnects from LiteLLM.

### Request Example:

```
DELETE https://<apigw_endpoint>/models/{modelId}
```

### Response Example:

```json
{
  "status": "success",
  "message": "Model mistral-vllm has been deleted successfully."
}
```

## Updating a Model

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

### Request Example

```
PUT https://<apigw_endpoint>/models/{modelId}
```

### Example Payloads

#### Update Model Metadata

This payload will simply update the model metadata, which will complete within seconds of invoking. If setting a model as an `embedding` model, then the
`streaming` option must be set to `false` or omitted as LISA does not support streaming with embedding models. Both the `streaming` and `modelType` options
may be included in any other update request.

```json
{
  "streaming": true,
  "modelType": "textgen"
}
```

#### Update AutoScaling Configuration

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

#### Stop Model - Scale Down to 0 Instances

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

#### Start Model - Restore Previous AutoScaling Configuration

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

## Model Scheduling (Admin API)

LISA provides comprehensive model scheduling capabilities that allow administrators to automatically start and stop LISA-hosted models on predefined schedules. This feature helps optimize infrastructure costs by ensuring models are only running when needed, while maintaining the flexibility to have different schedules for different days of the week.

### Schedule Types

LISA supports two scheduling types:

- **DAILY**: Configure different start/stop times for each day of the week. Each day can have its own schedule or be left unscheduled.
- **RECURRING**: Configure a single start/stop time that applies every day.

### Scheduling Endpoints

#### Creating/Updating a Schedule

Create or update a schedule for a specific model. This endpoint accepts the same payload for both creating new schedules and updating existing ones.

##### Request Example:

```
PUT https://<apigw_endpoint>/models/{modelId}/schedule
```

##### Example Payload for Daily Schedule:

```json
{
  "scheduleType": "DAILY",
  "timezone": "America/New_York",
  "dailySchedule": {
    "monday": {
      "startTime": "09:00",
      "stopTime": "17:00"
    },
    "tuesday": {
      "startTime": "09:00",
      "stopTime": "17:00"
    },
    "wednesday": {
      "startTime": "08:00",
      "stopTime": "18:00"
    },
    "friday": {
      "startTime": "09:00",
      "stopTime": "15:00"
    }
  }
}
```

##### Example Payload for Recurring Schedule:

```json
{
  "scheduleType": "RECURRING",
  "timezone": "America/New_York",
  "recurringSchedule": {
    "startTime": "08:00",
    "stopTime": "20:00"
  }
}
```

##### Response Example:

```json
{
  "message": "Schedule updated successfully",
  "modelId": "mistral-vllm",
  "scheduleEnabled": true
}
```

##### Key Fields for Schedule Configuration:

- `scheduleType`: Either "DAILY" or "RECURRING"
- `timezone`: IANA timezone identifier (e.g., "UTC", "America/New_York", "Europe/London")
- `dailySchedule`: For DAILY type - defines start/stop times for each day of the week
  - Days can be omitted if no schedule is needed for that day
  - Each day requires both `startTime` and `stopTime` in HH:MM format (24-hour)
  - Stop time must be at least 2 hours after start time
- `recurringSchedule`: For RECURRING type - defines single start/stop time applied daily
  - Requires both `startTime` and `stopTime` in HH:MM format (24-hour)
  - Stop time must be at least 2 hours after start time

#### Getting Schedule Configuration

Retrieve the current schedule configuration for a model.

##### Request Example:

```
GET https://<apigw_endpoint>/models/{modelId}/schedule
```

##### Response Example:

```json
{
  "modelId": "mistral-vllm",
  "scheduling": {
    "scheduleType": "DAILY",
    "timezone": "America/New_York",
    "dailySchedule": {
      "monday": {
        "startTime": "09:00",
        "stopTime": "17:00"
      },
      "tuesday": {
        "startTime": "09:00",
        "stopTime": "17:00"
      }
    },
    "scheduleEnabled": true,
    "scheduleConfigured": true,
    "lastScheduleUpdate": "2024-01-15T10:30:00Z"
  },
  "nextScheduledAction": {
    "action": "START",
    "scheduledTime": "2024-01-16T14:00:00Z"
  }
}
```

#### Getting Schedule Status

Get detailed status information about a model's scheduling configuration and current state.

##### Request Example:

```
GET https://<apigw_endpoint>/models/{modelId}/schedule/status
```

##### Response Example:

```json
{
  "modelId": "mistral-vllm",
  "scheduleEnabled": true,
  "scheduleConfigured": true,
  "lastScheduleFailed": false,
  "scheduleStatus": "ACTIVE",
  "scheduleType": "DAILY",
  "timezone": "America/New_York",
  "nextScheduledAction": {
    "action": "STOP",
    "scheduledTime": "2024-01-15T22:00:00Z"
  },
  "lastScheduleUpdate": "2024-01-15T10:30:00Z",
  "lastScheduleFailure": null
}
```

##### Schedule Status Fields:

- `scheduleEnabled`: Whether scheduling is currently active for the model
- `scheduleConfigured`: Whether a schedule has been configured for the model
- `lastScheduleFailed`: Whether the last scheduled action failed
- `scheduleStatus`: Overall status - "ACTIVE", "DISABLED", or "FAILED"
- `scheduleType`: The configured schedule type ("DAILY" or "RECURRING")
- `timezone`: Configured timezone for the schedule
- `nextScheduledAction`: Details about the next scheduled start/stop action
- `lastScheduleUpdate`: Timestamp of when the schedule was last modified
- `lastScheduleFailure`: Details about the most recent scheduling failure (if any)

#### Deleting a Schedule

Remove the schedule configuration for a model, disabling automatic start/stop functionality.

##### Request Example:

```
DELETE https://<apigw_endpoint>/models/{modelId}/schedule
```

##### Response Example:

```json
{
  "message": "Schedule deleted successfully",
  "modelId": "mistral-vllm",
  "scheduleEnabled": false
}
```

### Schedule Validation Rules

- **Time Format**: All times must be in HH:MM format using 24-hour notation (00:00 to 23:59)
- **Minimum Duration**: Stop time must be at least 2 hours after start time
- **Daily Schedule**: At least one day must have a schedule configured for DAILY type
- **Timezone**: Must be a valid IANA timezone identifier
- **Model Requirements**: Only LISA-hosted models with Auto Scaling Groups can be scheduled
- **Model State**: Models must be in "InService" or "Stopped" state to configure scheduling

### Schedule Behavior

- **Automatic Actions**: Models are automatically started and stopped according to their configured schedules
- **Cross-Day Schedules**: Schedules can span midnight (e.g., start at 23:00, stop at 01:00 next day)
- **Weekend Handling**: Days without configured schedules remain unaffected by scheduling
- **Failure Handling**: Failed schedule actions are logged and can be monitored via the status endpoint
- **Manual Override**: Manual start/stop operations work independently of scheduling
- **Update Handling**: Schedule updates take effect immediately and recalculate next actions
