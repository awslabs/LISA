# API Usage Overview

LISA provides robust API endpoints for managing models, both for users and administrators. These endpoints allow for
operations such as listing, creating, updating, and deleting models.

## API Gateway and ALB Endpoints

LISA uses two primary APIs for model management:

1. **[User-facing OpenAI-Compatible API](#litellm-routing-in-all-models)**: Available to all users for inference tasks
   and accessible through the
   LISA
   Serve ALB. This API provides an interface for querying and interacting with models deployed on Amazon ECS, Amazon
   Bedrock, or through LiteLLM.
2. **[Admin-level Model Management API](/config/model-management-api)**: Available only to administrators through the
   API Gateway (APIGW). This API
   allows for full control of model lifecycle management, including creating, updating, and deleting models.

### LiteLLM Routing in All Models

Every model request is routed through LiteLLM, regardless of whether infrastructure (like ECS) is created for it.
Whether deployed on ECS, external models via Bedrock, or managed through LiteLLM, all models are added to LiteLLM for
traffic routing. The distinction is whether infrastructure is created (determined by request payloads), but LiteLLM
integration is consistent for all models. The model management APIs will handle adding or removing model configurations
from LiteLLM, and the LISA Serve endpoint will handle the inference requests against models available in LiteLLM.

## User-facing OpenAI-Compatible API

The OpenAI-compatible API is accessible through the LISA Serve ALB and allows users to list models available for
inference tasks. Although not specifically part of the model management APIs, any model that is added or removed from
LiteLLM via the model management API Gateway APIs will be reflected immediately upon queries to LiteLLM through the LISA
Serve ALB.

### Listing Models

The `/v2/serve/models` endpoint on the LISA Serve ALB allows users to list all models available for inference in the
LISA system.

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

These fields are all defined by the OpenAI API specification, which is
documented [here](https://platform.openai.com/docs/api-reference/models/list).

- `id`: A unique identifier for the model.
- `object`: The type of object, which is "model" in this case.
- `created`: A Unix timestamp representing when the model was created.
- `owned_by`: The entity responsible for the model, such as "openai."
