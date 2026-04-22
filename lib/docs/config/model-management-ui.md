# Model Management UI

## Configuring Models

LISA's Model Management UI allows Administrators to configure models for use with LISA. LISA supports:

- third-party models hosted externally to LISA that are compatible with LiteLLM,
- customer internal hosted models exposed by an internal AWS load balancer URL, and
- self-hosted models running on LISA-managed Amazon ECS infrastructure.

LISA's Model Management wizard walks Administrators through configuration steps.

## Scaling Models

### Overview

LISA-hosted models run on Amazon ECS with EC2 Auto Scaling Groups (ASGs) that manage the underlying compute instances. Scaling configuration controls how many instances serve your model and how the system responds to changes in demand. Understanding these parameters helps you balance cost, availability, and performance for your workloads.

### Auto Scaling Architecture

Each LISA-hosted model is backed by:

- An ECS cluster with an Auto Scaling Group that manages EC2 instances
- An Application Load Balancer (ALB) that distributes traffic across instances
- A target tracking scaling policy that adjusts capacity based on ALB metrics

The ASG scales EC2 instances in and out, while ECS task count scaling ensures the right number of containers are running across those instances. Both layers use the same min/max capacity bounds.

### Auto Scaling Configuration Parameters

The following parameters are configurable through the Model Management UI under **Auto Scaling Configuration**:

| Parameter | Default | Description |
|-----------|---------|-------------|
| Min Capacity | 1 | Minimum number of instances. The ASG will never scale below this value. Must be at least 1. |
| Max Capacity | 2 | Maximum number of instances. The ASG will never scale above this value. Must be at least 1. |
| Desired Capacity | — | The target number of running instances. Typically managed automatically by the scaling policy. |
| Cooldown | 420s | Cool-down period in seconds between scaling activities. Prevents rapid scale-in/scale-out oscillation. |
| Default Instance Warmup | 180s | Time in seconds for a newly launched instance to warm up before it contributes to scaling metrics. Maximum 3600s (1 hour). Larger models (e.g. gpt-oss-120b) will require a significantly longer warmup period — potentially close to the maximum — due to the time needed to download and load model weights into GPU memory. |
| Block Device Volume Size | 50 GB | EBS volume size (in GB) attached to each instance. Minimum 30 GB. Larger models or those with significant disk I/O may need more. |

### Scaling Metrics

LISA supports two ALB-based scaling metrics. The metric determines what signal triggers scale-out and scale-in events:

| Metric | Best For | Statistic | Description |
|--------|----------|-----------|-------------|
| `RequestCountPerTarget` | Embedding models, high-throughput workloads | Sample Count | Scales based on the number of requests per target. Set `targetValue` to the max requests per instance before scaling out (default: 30). |
| `TargetResponseTime` | Text generation LLMs, latency-sensitive workloads | p90 | Scales based on response latency degradation. Set `targetValue` to the maximum acceptable p90 latency in seconds (e.g., 10). |

#### Metric Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| ALB Metric Name | `RequestCountPerTarget` | The ALB metric used for scaling decisions. |
| Target Value | 30 | Threshold for the chosen metric. Meaning depends on the metric: request count or latency in seconds. |
| Duration | 60s | Evaluation period in seconds for the metric. |
| Estimated Instance Warmup | 180s | Time in seconds until a newly launched instance begins sending metrics to CloudWatch. |

### Scaling Recommendations

#### Text Generation Models

- Use `TargetResponseTime` as the scaling metric
- Set `targetValue` to your acceptable p90 latency (e.g., 10 seconds)
- These models are compute-intensive with longer inference times, so latency-based scaling reacts to actual user impact
- Consider a higher `defaultInstanceWarmup` (300–3600s) since large models take time to load

#### Embedding Models

- Use `RequestCountPerTarget` as the scaling metric
- Embedding requests are typically fast and uniform, so request volume is a reliable scaling signal
- A lower `targetValue` (e.g., 20–50) keeps latency consistent under load

#### Cost Optimization

- Set `minCapacity` to 0 or 1 depending on whether you need always-on availability
- Use [Model Scheduling](#model-scheduling) to automatically stop models during off-hours
- Monitor actual utilization through CloudWatch to right-size `maxCapacity`
- Increase `cooldown` to avoid unnecessary scaling churn during bursty traffic

#### High Availability

- Set `minCapacity` to at least 2 for production workloads to survive a single instance failure
- Ensure `maxCapacity` provides enough headroom for peak traffic
- Keep `defaultInstanceWarmup` accurate to avoid premature traffic routing to cold instances

### Modifying Scaling Configuration

Auto scaling parameters can be updated on running models without requiring a container restart. See [Update Capabilities by Hosting Type](#update-capabilities-by-hosting-type) for the full list of no-interruption updates.

1. Navigate to `Administration` &#8594; `Model Management`
2. Select the target model
3. Select `Actions` &#8594; `Update`
4. Navigate to **Auto Scaling Configuration** in the update wizard
5. Adjust parameters as needed
6. Submit the update

The system validates that `minCapacity` does not exceed `maxCapacity` before applying changes.

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

LISA provides scheduling options for self-hosted models. Administrators establish automated start and stop times which auto-suspend resources. Model scheduling helps optimize infrastructure costs by ensuring models are only running when needed. Administrators have the flexibility to set daily start and stop times, or establish a recurring schedule.

### Scheduling Types

LISA supports two scheduling types. One type may be applied to each self-hosted model. If a schedule is not applied to a model, that model is either suspended or running 24/7 until an Administrator manually changes its state.

- **Daily Scheduling**: Configure different start and stop times for each day of the week. Each day can have its own unique schedule or be left unscheduled.
- **Recurring Scheduling**: Configure a single start and stop time that applies to every day of the week.

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
   - You will see the resource scheduling view where scheduling is configured

2. **Choose Schedule Type**
   - **Daily Schedule**: Select this to configure different start and stop times for each day of the week
   - **Recurring Schedule**: Select this to configure the same start and stop time for every day

3. **Configure Schedule Parameters**

   **For Daily Schedules**:
   - Select the timezone for your schedule. LISA supports all IANA timezone identifiers
   - Configure start and stop times for each desired day of the week in HH:MM format (24-hour)
   - Days can be left blank if no scheduling is needed for that day. The model will remain suspended until it is started again

   **For Recurring Schedules**:
   - Select the timezone for your schedule
   - Configure a single start time and stop time that will apply to every day
   - Times must be in HH:MM format (24-hour notation)

4. **Validate Configuration**
   - The UI validates that stop times are at least 2 hours after start times in a single day
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

Model Management displays schedule information:

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

- Use meaningful time buffers like a minimum of 2-hours between starting and stopping within a single day
- For operations spanning midnight, split schedules across consecutive days (e.g., Monday 21:00-23:59, Tuesday 00:00-03:00)
- Plan for holiday and special event schedule modifications
- Implement gradual rollout of new schedules across model fleet
- Consider small gaps between consecutive day schedules to avoid brief service interruptions (e.g., Monday ends 23:58, Tuesday starts 00:01)
