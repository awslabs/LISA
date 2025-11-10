# Guardrails

## Overview

Guardrails in LISA provide a powerful way to ensure safe and compliant model outputs through integration with AWS Bedrock Guardrails via LiteLLM. Guardrails can validate, filter, and control both input prompts and model responses, helping you enforce content policies, protect sensitive information, and maintain compliance standards.

## Key Features

- **AWS Bedrock Integration**: Leverages AWS Bedrock Guardrails for robust content filtering
- **Flexible Application Modes**: Apply guardrails `pre-call`, `during-call`, or `post-call`
- **Group-Based Access Control**: Target specific user groups with different guardrail policies
- **Per-Model Configuration**: Each model can have multiple guardrails with different settings
- **Automatic Application**: Guardrails are automatically applied based on user group membership

## Architecture

### Data Storage

Guardrails are stored in a dedicated DynamoDB table with the following structure:

- **Partition Key**: `guardrailId` (LiteLLM-generated unique identifier)
- **Sort Key**: `modelId` (the model this guardrail is associated with)
- **Global Secondary Index**: `ModelIdIndex` (allows querying all guardrails for a specific model)

### Guardrail Application Flow

1. **User Request**: User sends a request to invoke a model
2. **Group Extraction**: System extracts user's group memberships from JWT token
3. **Guardrail Lookup**: System queries DynamoDB for guardrails associated with the model
4. **Group Matching**: System determines which guardrails apply based on:
   - Public guardrails (no `allowedGroups` specified) apply to all users
   - Private guardrails apply only if user belongs to at least one `allowedGroups`
5. **Guardrail Injection**: Applicable guardrail are added to the LiteLLM request
6. **Validation**: AWS Bedrock Guardrails validate the request/response
7. **Response Handling**: If a guardrail is triggered, the admin configured guardrail response is returned

## Prerequisites: Creating Guardrails in AWS Bedrock Console

Before you can attach guardrails to models in LISA, you must first create the guardrails in the AWS Bedrock Console.

### Steps to Create a Guardrail in AWS Bedrock Console

1. **Navigate to AWS Bedrock Console**
   - Open the AWS Console
   - Navigate to Amazon Bedrock service
   - Select "Guardrails" from the left navigation menu

2. **Create a New Guardrail**
   - Click "Create guardrail"
   - Provide a name for your guardrail
   - Define blocked messaging responses
   - Configure guardrail policies:
     - **Content filters**: Filter harmful content categories (hate, insults, sexual, violence, etc.)
     - **Denied topics**: Define topics to block
     - **Word filters**: Block or redact specific words/phrases
     - **Sensitive information filters**: Redact PII (email, phone, SSN, etc.)
     - **Contextual grounding**: Prevent hallucinations and ensure relevance

3. **Configure Guardrail Settings**
   - Configure version (`DRAFT` or numbered version)

4. **Test Your Guardrail**
   - Use the AWS Console's test functionality
   - Verify the guardrail behaves as expected

5. **Note the Guardrail Details**
   - Copy the **Guardrail ID** (e.g., `abc123xyz`)
   - Note the **Guardrail Version** (e.g., `DRAFT`, `1`, `2`)
   - Alternatively, copy the full **Guardrail ARN**

## Guardrail Configuration

### Configuration Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `guardrailName` | string | Yes | Friendly name for the guardrail in LISA |
| `guardrailIdentifier` | string | Yes | AWS Bedrock Guardrail ARN or ID |
| `guardrailVersion` | string | No | Version to use (default: "DRAFT") |
| `mode` | string | No | When to apply: "pre_call", "during_call", or "post_call" (default: "pre_call") |
| `description` | string | No | Human-readable description of the guardrail's purpose |
| `allowedGroups` | array | No | List of user groups this guardrail applies to (empty = public) |

### Guardrail Modes

- `pre_call`: Validates input prompts before sending to the model
- `during_call`: Validates during model processing (streaming scenarios)
- `post_call`: Validates model responses after generation

## Managing Guardrails via LISA Models API

### Creating a Model with Guardrails

Guardrails are attached to models as part of the model creation process. Include the `guardrailsConfig` field in your model creation request to apply a guardrail to a model:

```bash
POST /{deploymentStage}/models

{
  "modelId": "my-model-id",
  "modelName": "MyModel",
  "streaming": true,
  "features": [],
  "modelType": "textgen",
  "guardrailsConfig": {
    "guardrail-1": {
      "guardrailName": "ContentFilter",
      "guardrailIdentifier": "abc123xyz",
      "guardrailVersion": "1",
      "mode": "pre_call",
      "description": "Filters harmful content from user inputs",
      "allowedGroups": ["team-a", "team-b"]
    },
    "guardrail-2": {
      "guardrailName": "PIIProtection",
      "guardrailIdentifier": "arn:aws:bedrock:us-east-1:123456789012:guardrail/xyz789",
      "guardrailVersion": "DRAFT",
      "mode": "post_call",
      "description": "Redacts PII from model responses",
      "allowedGroups": []
    }
  }
}
```

**Notes:**
- The guardrail key (e.g., "guardrail-1") is an internal identifier
- `guardrailIdentifier` must match an existing AWS Bedrock Guardrail
- Empty `allowedGroups` means the guardrail applies to all users
- Multiple guardrails can be configured per model
- Guardrails are automatically registered in LiteLLM during model creation

### Listing Guardrails

#### List All Guardrails via LiteLLM API

To view all guardrails registered in LiteLLM:

```bash
GET /v2/serve/v2/guardrails/list
```

This endpoint queries LiteLLM directly and returns all registered guardrails across all models.

### Updating Guardrails

Update guardrails by sending a PUT request to update the model:

```bash
PUT /{deploymentStage}/models/{modelId}

{
  "guardrailsConfig": {
    "guardrail-1": {
      "guardrailName": "ContentFilter",
      "guardrailIdentifier": "abc123xyz",
      "guardrailVersion": "2",
      "mode": "pre_call",
      "description": "Updated content filter with stricter rules",
      "allowedGroups": ["team-a", "team-b", "team-c"]
    }
  }
}
```

**Update Operations:**

1. **Modify Existing Guardrail**: Include the guardrail with updated values
2. **Add New Guardrail**: Include a new guardrail key with complete configuration
3. **Remove Guardrail**: Set `markedForDeletion: true` on the guardrail

### Deleting Guardrails

Guardrails are deleted when their associated model is deleted or when they are marked for deletion:

```bash
PUT /{deploymentStage}/models/{modelId}

{
  "guardrailsConfig": {
    "guardrail-1": {
      "guardrailName": "ContentFilter",
      "guardrailIdentifier": "abc123xyz",
      "markedForDeletion": true
    }
  }
}
```

This operation:
1. Removes the guardrail from LiteLLM
2. Deletes all associated guardrails from DynamoDB
3. Removes guardrail configurations from LiteLLM

**Note**: Deleting a model does NOT delete the underlying AWS Bedrock Guardrail. It only removes the association between the guardrail and the LISA model and removes the guardrail from LiteLLM.

## Managing Guardrails via UI

### Creating Guardrails During Model Creation

1. **Create the Guardrail in AWS Bedrock Console first** (see Prerequisites section)
2. Navigate to **Model Management** and select **Create Model**
3. Fill in the base model configuration
4. Navigate to **Guardrails Configuration**
5. Click **Add Guardrail**
6. Configure the guardrail:
   - **Guardrail Name**: Enter a friendly name
   - **Guardrail Identifier**: Enter the AWS Bedrock Guardrail ARN or ID (from AWS Console)
   - **Guardrail Version**: Specify version (default: DRAFT)
   - **Mode**: Select when to apply (Pre Call, During Call, or Post Call)
   - **Description** (optional): Describe the guardrail's purpose
   - **Allowed Groups** (optional): Add group names that should have this guardrail
7. Click **Add** to add groups, or press Enter after typing a group name
8. Repeat steps 6-8 to add multiple guardrails
9.  Finish remaining configuration steps
10. Click **Create Model** to finalize

### Viewing Guardrails

1. Navigate to **Model Management**
2. Select a model card
3. Select **Actions** and then **Update**
4. Guardrails will be displayed in the model details under **Guardrails Configuration**

### Updating / Removing Guardrails

1. Navigate to **Model Management**
2. Select the model card of the model you want to update
3. Select **Actions** and then **Update**
4. Navigate to **Guardrails Configuration**
5. Modify existing guardrails
6. Add new guardrails using the **Add Guardrail** button
7. Remove guardrails by clicking the **X** button
8. Navigate to final page and click **Update Model** to save changes

**Note**: When editing a model, clicking the X button marks guardrails for deletion rather than removing them immediately. They will be deleted when you save the model.

## Best Practices

### 1. Design Guardrails in AWS Bedrock First

- Test guardrails thoroughly in AWS Bedrock Console before attaching to models
- Create separate guardrails for different purposes (content filtering, PII, compliance)
- Use descriptive names to identify guardrail purposes

### 2. Use Group-Based Access Appropriately

- Start with public guardrails for baseline protection
- Add team-specific guardrails for specialized requirements
- Document which groups require which guardrails
- Regularly audit group memberships

### 3. Monitor and Iterate

- Adjust guardrail sensitivity based on false positives/negatives
- Update guardrails in AWS Bedrock as policies and requirements evolve
- Update model configurations in LISA to use new guardrail versions

## Troubleshooting

### Guardrails Not Being Applied

**Symptom**: Requests are not being filtered as expected

**Possible Causes**:
1. Guardrail doesn't exist in AWS Bedrock
2. Guardrail identifier is incorrect
3. Guardrail is not attached to model
4. Guardrail version attached to model is incorrect
4. User is not a member of the required groups
5. AWS Bedrock Guardrail is not accessible from LISA VPC

**Resolution**:
1. Verify guardrail exists in AWS Bedrock Console
2. Check guardrail identifier configured in LISA matches AWS Bedrock Console
3. Verify user group memberships
4. Check guardrail configuration in model details
5. Check CloudWatch logs for errors
6. Check REST ECS Container for errors

### Guardrail Updates Not Taking Effect

**Symptom**: Updated guardrail configuration not being applied

**Possible Causes**:
1. Model update did not complete successfully
2. Guardrail changes made in AWS Bedrock but version not updated in LISA
3. Cache issues with model configuration

**Resolution**:
1. Check model status (should be "In Service")
2. Verify `guardrailVersion` in LISA matches the version in AWS Bedrock
3. Check state machine execution logs
4. Verify guardrail configuration

### Invalid Guardrail Identifier Error

**Symptom**: Error during model creation or update mentioning invalid guardrail

**Possible Causes**:
1. Guardrail doesn't exist in AWS Bedrock
2. Incorrect guardrail ID or ARN
3. Guardrail in different AWS region

**Resolution**:
1. Verify guardrail exists in AWS Bedrock Console in the correct region
2. Copy guardrail identifier directly from AWS Console

### High Latency with Guardrails

**Symptom**: Requests take significantly longer with guardrails enabled

**Possible Causes**:
1. Too many guardrails configured
2. Complex guardrail rules in AWS Bedrock

**Resolution**:
1. Reduce number of guardrails where possible
2. Optimize guardrail rules in AWS Bedrock Console
3. Consider using only critical guardrails for performance-sensitive applications

## Additional Resources

- [AWS Bedrock Guardrails Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [LiteLLM Guardrails API](https://litellm-api.up.railway.app/#/Guardrails)
- LISA Model Management API Documentation
