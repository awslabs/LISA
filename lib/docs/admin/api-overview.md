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
curl -s -H 'Authorization: Bearer <your_token>' -X GET https://<apigw_endpoint>/v2/serve/models
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

## Metrics API Gateway Endpoints

LISA provides RESTful API endpoints for programmatic access to user metrics data. These endpoints enable administrators and applications to retrieve detailed analytics and usage statistics.

### Base URL Structure

All metrics endpoints are accessed through LISA's main API Gateway with the following structure:
```
https://{API-GATEWAY-DOMAIN}/{STAGE}/metrics/users/
```

### Authentication

All API endpoints require proper authentication through LISA's configured authorization mechanism. Ensure your requests include valid authorization headers as configured in your LISA deployment.

### Available Endpoints

#### **Get Individual User Metrics**

**Endpoint**: `GET /metrics/users/{userId}`
**Integrated Lambda Function**: `get_user_metrics`
**Description**: Retrieves comprehensive metrics data for a specific user, including session-level details and usage history.

**Path Parameters**:
- `userId` (string, required): The unique identifier for the user whose metrics you want to retrieve

**Example Request**:
```bash
curl -X GET \
  'https://your-api-gateway-domain/metrics/users/john.doe@company.com' \
  -H 'Authorization: Bearer {YOUR-AUTH-TOKEN}'
```

**Response Format**:
```json
{
    "statusCode": 200,
    "body": {
        "johnDoe": {
            "totalPrompts": 20.0,
            "ragUsageCount": 1.0,
            "mcpToolCallsCount": 12.0,
            "mcpToolUsage": {
                "GMAIL-SEND-EMAIL": 11.0,
                "GOOGLE_CALENDAR-LIST-EVENTS": 1.0
            },
            "userGroups": [
                "lisa-enjoyers",
                "coffee-lovers"
            ],
            "sessionMetrics": {
                "c6d20198-b1b1-46d9-8bec-3ddaafeb96a6": {
                    "ragUsage": 0.0,
                    "mcpToolUsage": {
                        "GMAIL-SEND-EMAIL": 3.0
                    },
                    "totalPrompts": 5.0,
                    "mcpToolCallsCount": 3.0
                }
            },
            "firstSeen": "2025-07-01T16:47:21.171855",
            "lastSeen": "2025-07-17T19:51:16.036882"
        }
    }
}
```

**Response Fields**:
- `totalPrompts`: Total number of prompts submitted by the user
- `ragUsageCount`: Number of times the user utilized RAG features
- `mcpToolCallsCount`: Total MCP tool calls made by the user
- `mcpToolUsage`: Breakdown of usage by individual MCP tools
- `userGroups`: List of organizational groups the user belongs to
- `sessionMetrics`: Detailed metrics for each user session
- `firstSeen`: Timestamp of user's first interaction with LISA
- `lastSeen`: Timestamp of user's most recent interaction

**Error Responses**:
- `400 Bad Request`: Missing or invalid userId parameter
- `404 Not Found`: User not found in metrics database
- `500 Internal Server Error`: Database or system error

#### **Get All Users Metrics**

**Endpoint**: `GET /metrics/users/all`
**Lambda Function**: `get_user_metrics_all`
**Description**: Retrieves aggregated metrics across all users in the system, providing system-wide analytics and usage statistics.

**Example Request**:
```bash
curl -X GET \
  'https://your-api-gateway-domain/metrics/users/all' \
  -H 'Authorization: Bearer {YOUR-AUTH-TOKEN}'
```

**Response Format**:
```json
{
    "statusCode": 200,
    "body": {
        "totalUniqueUsers": 3,
        "totalPrompts": 31.0,
        "totalRagUsage": 1.0,
        "ragUsagePercentage": 3.225806451612903,
        "totalMCPToolCalls": 12.0,
        "mcpToolCallsPercentage": 38.70967741935484,
        "mcpToolUsage": {
            "GMAIL-SEND-EMAIL": 11.0,
            "GOOGLE_CALENDAR-LIST-EVENTS": 1.0
        },
        "userGroups": {
            "tea-lovers": 2,
            "lisa-enjoyers": 2,
            "coffee-lovers": 1
        }
    }
}
```

**Response Fields**:
- `totalUniqueUsers`: Count of unique users who have interacted with LISA
- `totalPrompts`: Aggregate count of all prompts across users
- `totalRagUsage`: Total number of RAG feature uses
- `ragUsagePercentage`: Percentage of prompts that utilized RAG
- `totalMCPToolCalls`: Total MCP tool calls across all users
- `mcpToolCallsPercentage`: Percentage of prompts that included MCP tool usage
- `mcpToolUsage`: System-wide breakdown of MCP tool usage by tool name
- `userGroups`: Distribution of users across organizational groups

**Error Responses**:
- `500 Internal Server Error`: Database scan error or system failure


# Error Handling for API Requests

In the LISA model management API, error handling is designed to ensure robustness and consistent responses when errors occur during the execution of API requests. This section provides a detailed explanation of the error handling mechanisms in place, including the types of errors that are managed, how they are raised, and what kind of responses clients can expect when these errors occur.

## Common Errors and Their HTTP Responses

Below is a list of common errors that can occur in the system, along with the HTTP status codes and response structures that are returned to the client.

### ModelNotFoundError

* **Description**: Raised when a model that is requested for retrieval or deletion is not found in the system.
* **HTTP Status Code**: `404 Not Found`
* **Response Body**:

```json
{
    "error": "ModelNotFoundError",
    "message": "The requested model with ID <model_id> could not be found."
}
```

* **Example Scenario**: When a client attempts to fetch details of a model that does not exist in the database, the `ModelNotFoundError` is raised.

### ModelAlreadyExistsError

* **Description:** Raised when a request to create a model is made, but the model already exists in the system.
* **HTTP Status Code**: `400`
* **Response Body**:

```json
{
    "error": "ModelAlreadyExistsError",
    "message": "A model with the given configuration already exists."
}
```

* **Example Scenario:** A client attempts to create a model with an ID or name that already exists in the database. The system detects the conflict and raises the `ModelAlreadyExistsError`.

### InvalidInputError (Hypothetical Example)

* **Description**: Raised when the input provided by the client for creating or updating a model is invalid or does not conform to expected formats.
* **HTTP Status Code**: `400 Bad Request`
* **Response Body**:

```json
{
    "error": "InvalidInputError",
    "message": "The input provided is invalid. Please check the required fields and formats."
}
```

* **Example Scenario**: The client submits a malformed JSON body or omits required fields in a model creation request, triggering an `InvalidInputError`.

## Handling Validation Errors

Validation errors are handled across the API via utility functions and model transformation logic. These errors typically occur when user inputs fail validation checks or when required data is missing from a request.

### Example Response for Validation Error:

* **HTTP Status Code**: `422 Unprocessable Entity`
* **Response Body**:

```json
{
    "error": "ValidationError",
    "message": "The input provided does not meet the required validation criteria."
}
```
