# Model Management UI

## Configuring Models

LISA's Model Management UI allows Administrators to configure models for use with LISA.  LISA supports third party models that are hosted externally to LISA that are compatible with LiteLLM. LISA also supports self-hosting models within Amazon ECS. LISA's Model Management wizard walks Administrators through configuration steps.


## Updating Models

### Overview

Through LISA's Model Management UI, Administrators can update the configuration of running models, to include their underlying infrastructure, without requiring a complete redeployment. Updates are processed through the `UpdateModel` state machine.

### Update Considerations

> [!WARNING]
> Updates to a LISA-hosted model's Container Configuration require a container restart in order to pick up the newly generated task definition. **This will result in a temporary outage**. Administrators must acknowldge this risk on the final step of the update wizard in order to submit the request.

Models undergoing updating will not be selectable from the Chat UI. Users with existing sessions to the model being updated should expect to see errors returned when trying to prompt the model mid-update.

Updated models automatically become available in the Chat UI once updates complete and status returns to `InService`.

### Update Capabilities by Hosting Type

| Update Category | Capability | Third-Party Models | LISA-Hosted Models | Service Impact |
|-----------------|------------|-------------------|-------------------|----------------|
| **Metadata Updates** | Model Description | ✅ | ✅ | No interruption |
| | Allowed Groups | ✅ | ✅ | No interruption |
| | Summarization Capabilities | ✅ | ✅ | No interruption |
| **Model Features** | Streaming | ✅ | ✅ | No interruption |
| | Tool Calls | ✅ | ✅ | No interruption |
| | Image Input | ✅ | ✅ | No interruption |
| | Summarization | ✅ | ✅ | No interruption |
| **Auto-Scaling Configuration** | Min Capacity | ❌ | ✅ | No interruption |
| | Max Capacity | ❌ | ✅ | No interruption |
| | Desired Capacity | ❌ | ✅ | No interruption |
| | Cooldown | ❌ | ✅ | No interruption |
| | Default Instance Warmup | ❌ | ✅ | No interruption |
| **Container Configuration** | Container Environment Variables | ❌ | ✅ | ECS restart required |
| | Shared Memory Size | ❌ | ✅ | ECS restart required |
| | Health Check Commands | ❌ | ✅ | ECS restart required |
| | Health Check Interval | ❌ | ✅ | ECS restart required |
| | Health Check Start Period | ❌ | ✅ | ECS restart required |
| | Health Check Timeout | ❌ | ✅ | ECS restart required |
| | Health Check Retries | ❌ | ✅ | ECS restart required |
| **Model Lifecycle** | Start/Stop Models | ❌ | ✅ | Service interruption |

### Update Process Flow

#### 1. Validation Phase
The system validates update requests against current model state:
- Ensures model is in `InService` or `Stopped` state
- Validates configuration conflicts
- Checks capacity constraints against existing auto-scaling groups
- Verifies container configuration compatibility

#### 2. State Machine Orchestration
Updates are processed through a multi-step state machine:

**Step 1 - Job Intake**:
- Processes update payload
- Determines required update types
- Sets model status to `Updating`
- Prepares infrastructure changes

**Step 2 - ECS Updates** (if needed):
- Creates new task definition with updated container config
- Updates ECS service
- Monitors deployment progress
- Handles rollback on failures

**Step 3 - Capacity Updates** (if needed):
- Updates auto-scaling group parameters
- Monitors instance health and availability
- Waits for capacity stabilization

**Step 4 - Finalization**:
- Updates model metadata in database
- Restores model to `InService` status
- Registers model with inference endpoint if needed

#### 3. Safety Mechanisms

**State Validation**:
- Models cannot be updated during transitional states
- Updates requiring a container restart require explicit acknowledgment

**Rollback Protection**:
- Failed deployments automatically scale down to prevent resource waste
- ECS updates include deployment monitoring with timeout protection
- Database state is preserved during failures

**Resource Limits**:
- Polling timeouts prevent infinite waiting
- Capacity changes validate against AWS account limits
- Container updates respect ECS service constraints

### Performing Model Updates

#### Prerequisites
- Administrator access to LISA Model Management
- Target model is in `InService` or `Stopped` state
- Understanding of update impact (restart requirements)

#### Update Procedure

1. **Access Model Management UI**
   - Navigate to `Administration` &#8594; `Model Management`
   - Select the target model
   - Select `Actions` &#8594; `Update`

2. **Configuration Update**
   - Use the multi-step update wizard to navigate through updatable configurations
   - Review and Update the current model configurations

3. **Submit Updates**
   - Acknowledge the ECS restart warnings (if applicable)
   - Review changes in final step
   - Submit for processing

4. **Monitor Progress**
   - Model status will change to `Updating`
   - Monitor through the Model Management UI (auto-refreshes every 30 seconds)

### Troubleshooting Update Issues

#### Common Update Failures

**Validation Errors**:
- Model in wrong state for updates
- Configuration conflicts (e.g., min > max capacity)
- Invalid container configurations

**Deployment Issues**:
- ECS deployment timeouts
- Health check failures
- Resource constraints

**Capacity Problems**:
- Auto-scaling group update failures
- Instance launch issues
- Load balancer target group problems

#### Resolution Steps

1. **Check Model Status**: Ensure model is in an updatable state
2. **Review Configuration**: Validate all parameters against AWS limits
3. **Check State Machine Execution**: Check the recent executions of the `UpdateModel` state machine for any failures
4. **Monitor Logs**: Check CloudWatch logs for any detailed error information
