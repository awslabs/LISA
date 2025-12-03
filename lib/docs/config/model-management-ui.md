# Model Management UI

## Configuring Models

LISA's Model Management UI allows Administrators to configure models for use with LISA.  LISA supports third party models that are hosted externally to LISA that are compatible with LiteLLM. LISA also supports self-hosting models within Amazon ECS. LISA's Model Management wizard walks Administrators through configuration steps.


## Updating Models

### Overview

Through LISA's Model Management UI, Administrators can update the configuration of running models, to include their underlying infrastructure, without requiring a complete redeployment. Updates are processed through the `UpdateModel` state machine.

### Update Considerations

> [!WARNING]
> Updates to a LISA-hosted model's Container Configuration require a container restart in order to pick up the newly generated task definition. **This will result in a temporary outage**. Administrators must acknowledge this risk on the final step of the update wizard in order to submit the request.

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
| **Model Scheduling** | Configure Schedules | ❌ | ✅ | No interruption |
| | View Schedule Status | ❌ | ✅ | No interruption |
| | Delete Schedules | ❌ | ✅ | No interruption |

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

## Model Scheduling

### Overview

LISA's Model Management UI provides comprehensive scheduling capabilities for LISA-hosted models, allowing administrators to automatically start and stop models based on predefined schedules. This feature helps optimize infrastructure costs by ensuring models are only running when needed, while providing the flexibility to configure different schedules for different days of the week.

### Scheduling Types

LISA supports two scheduling approaches:

- **Daily Scheduling**: Configure different start/stop times for each day of the week. Each day can have its own unique schedule or be left unscheduled.
- **Recurring Scheduling**: Configure a single start/stop time that applies to every day of the week.

### Schedule Configuration

#### Prerequisites
- Administrator access to LISA Model Management
- Target model must be a LISA-hosted model
- Model must be in `InService` or `Stopped` state
- Model must have an Auto Scaling Group configured

#### Configuring a Schedule

1. **Access Scheduling Interface**
   - Navigate to `Administration` &#8594; `Model Management`
   - Click on the target LISA-hosted model
   - Click the `Actions` button
   - Click `Update`
   - In the modal, click on `Auto Scaling Configuration`
   - You will see the resource scheduling view where you can configure scheduling

2. **Choose Schedule Type**
   - **Daily Schedule**: Select this to configure different times for each day of the week
   - **Recurring Schedule**: Select this to configure the same time for every day

3. **Configure Schedule Parameters**

   **For Daily Schedules**:
   - Select the timezone for your schedule (supports all IANA timezone identifiers)
   - Configure start and stop times for each desired day of the week
   - Days can be left blank if no scheduling is needed for that day
   - Each configured day requires both start and stop times in HH:MM format (24-hour)

   **For Recurring Schedules**:
   - Select the timezone for your schedule
   - Configure a single start time and stop time that will apply every day
   - Times must be in HH:MM format (24-hour notation)

4. **Validate Configuration**
   - The UI validates that stop times are at least 2 hours after start times
   - For daily schedules, at least one day must have a schedule configured
   - Timezone selection is validated against IANA timezone database

5. **Submit Schedule**
   - Review the schedule configuration
   - Submit the schedule to activate automatic start/stop functionality

#### Schedule Configuration Examples

**Daily Schedule Example**:
- Monday-Friday: 09:00 to 17:00 (business hours)
- Saturday: 10:00 to 14:00 (reduced hours)
- Sunday: No schedule (model is in `Stopped` state)

**Recurring Schedule Example**:
- Every day: 08:00 to 20:00
- Applies consistently across all days of the week

### Managing Schedules

#### Viewing Schedule Status

The Model Management UI displays comprehensive schedule information:

- **Schedule Status Badge**: Shows current scheduling state (Active, Disabled, Failed)
- **Schedule Type**: Indicates whether the model uses Daily or Recurring scheduling
- **Timezone**: Shows the configured timezone for schedule calculations
- **Last Update**: Timestamp of the most recent schedule modification

#### Updating Existing Schedules

1. **Access Existing Schedule**
   - Navigate to the model with an existing schedule
   - Click on the model to select it
   - Click the `Actions` button
   - Click `Update`
   - In the modal, click on `Auto Scaling Configuration`
   - You will see the resource scheduling view

2. **Modify Configuration**
   - Update schedule type, times, timezone, or day configurations
   - Changes take effect immediately and recalculate next scheduled actions
   - The UI will show the updated "Next Scheduled Action" after saving

3. **Save Changes**
   - Review the modified schedule
   - Submit changes to update the automatic scheduling

#### Deleting Schedules

1. **Access Schedule Management**
   - Navigate to the scheduled model
   - Click on the model to select it
   - Click the `Actions` button
   - Click `Update`
   - In the modal, click on `Auto Scaling Configuration`
   - You will see the resource scheduling view

2. **Remove Scheduling**
   - In the resource scheduling view, toggle off Auto Scaling or clear the schedule configuration
   - This will disable automatic start/stop functionality
   - The model will remain in its current state after schedule removal

### Schedule Behavior and Rules

#### Time Format Requirements
- All times must be in 24-hour format (HH:MM)
- Valid range: 00:00 to 23:59
- Start time must be before stop time within the same day
- Stop time must be at least 2 hours after start time

#### Schedule Execution
- **Automatic Actions**: Models are automatically started and stopped according to configured schedules
- **Immediate Effect**: Schedule updates take effect immediately and recalculate next actions
- **Manual Override**: Manual start/stop operations work independently and don't affect scheduling
- **State Preservation**: Unscheduled days maintain the model's current state

#### Timezone Handling
- Schedules respect the configured timezone for all calculations
- Supports all IANA timezone identifiers (e.g., "UTC", "America/New_York", "Europe/London")
- Automatically handles daylight saving time transitions
- Schedule times are displayed in the configured timezone within the UI

### Monitoring and Troubleshooting

#### Schedule Status Indicators

The UI provides several indicators for schedule health:

- **Active**: Schedule is configured and working properly
- **Disabled**: No schedule is configured for the model
- **Failed**: Last scheduled action failed - check logs for details

#### Common Scheduling Issues

**Schedule Configuration Errors**:
- Invalid timezone selection
- Stop time less than 2 hours after start time
- No days configured for daily schedules

**Schedule Execution Failures**:
- Model in invalid state during scheduled action
- AWS service limits preventing scaling operations
- Network connectivity issues affecting schedule execution

#### Troubleshooting Steps

1. **Check Schedule Status**: Monitor the schedule status badge in the Model Management UI
2. **Review Next Scheduled Action**: Verify that upcoming actions are calculated correctly
3. **Validate Model State**: Ensure the model is in a valid state for scheduling operations
4. **Monitor Model Events**: Check the model's event history for scheduling-related activities
5. **Check AWS Logs**: Review CloudWatch logs for detailed error information about failed schedule executions

### Best Practices

#### Cost Optimization
- Configure schedules to match actual usage patterns
- Use daily scheduling for models with varying weekday/weekend usage
- Consider time zone alignment with primary user base
- Monitor actual vs. scheduled usage to refine schedules

#### Operational Considerations
- Allow sufficient warmup time after scheduled starts before peak usage
- Coordinate scheduled actions with maintenance windows
- Test schedule configurations in non-production environments first
- Document schedule configurations for operational handoff

#### Schedule Design
- Use meaningful time buffers (minimum 2-hour duration requirement exists for good reason)
- For operations spanning midnight, split schedules across consecutive days (e.g., Monday 21:00-23:59, Tuesday 00:00-03:00)
- Plan for holiday and special event schedule modifications
- Implement gradual rollout of new schedules across model fleet
- Consider small gaps between consecutive day schedules to avoid brief service interruptions (e.g., Monday ends 23:58, Tuesday starts 00:01)
