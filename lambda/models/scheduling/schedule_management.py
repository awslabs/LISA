import json
import logging
import boto3
import os
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, List, Optional
from botocore.config import Config
from botocore.exceptions import ClientError
from models.domain_objects import ScheduleType, SchedulingConfig, DaySchedule, WeeklySchedule

logger = logging.getLogger(__name__)

retry_config = Config(region_name=os.environ.get("AWS_REGION", "us-east-1"), retries={"max_attempts": 3, "mode": "adaptive"})
autoscaling_client = boto3.client("autoscaling", config=retry_config)
dynamodb = boto3.resource("dynamodb", config=retry_config)
model_table = dynamodb.Table(os.environ.get("MODEL_TABLE_NAME"))

class ScheduleManagementError(Exception):
    """Exception for schedule operations"""
    pass

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for schedule management operations"""
    try:
        logger.info(f"Processing schedule management request: {json.dumps(event, default=str)}")
        
        # Extract operation and parameters
        operation = event.get("operation")
        model_id = event.get("modelId")
        
        if not operation or not model_id:
            raise ValueError("Both 'operation' and 'modelId' are required")
        
        # Route to appropriate handler
        if operation == "create":
            return create_schedule(event)
        elif operation == "update":
            return update_schedule(event)
        elif operation == "delete":
            return delete_schedule(event)
        elif operation == "get":
            return get_schedule(event)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
            
    except Exception as e:
        logger.error(f"Schedule management error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "ScheduleManagementError",
                "message": str(e)
            })
        }


def create_schedule(event: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new schedule for a model"""
    model_id = event["modelId"]
    schedule_config = event.get("scheduleConfig")
    auto_scaling_group = event.get("autoScalingGroup")
    
    if not schedule_config:
        raise ValueError("scheduleConfig is required for create operation")
    
    if not auto_scaling_group:
        raise ValueError("autoScalingGroup is required for create operation")
    
    try:
        # Validate schedule configuration
        scheduling_config = SchedulingConfig(**schedule_config)
        
        # Create Auto Scaling scheduled actions
        scheduled_action_arns = create_scheduled_actions(
            model_id=model_id,
            auto_scaling_group=auto_scaling_group,
            schedule_config=scheduling_config
        )
        
        # Update model record with schedule information
        update_model_schedule_record(
            model_id=model_id,
            scheduling_config=scheduling_config,
            scheduled_action_arns=scheduled_action_arns,
            enabled=True
        )
        
        logger.info(f"Successfully created schedule for model {model_id} with {len(scheduled_action_arns)} actions")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Schedule created successfully",
                "modelId": model_id,
                "scheduledActionArns": scheduled_action_arns,
                "scheduleEnabled": True
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to create schedule for model {model_id}: {str(e)}")
        raise ScheduleManagementError(f"Failed to create schedule: {str(e)}")


def update_schedule(event: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing schedule for a model"""
    model_id = event["modelId"]
    schedule_config = event.get("scheduleConfig")
    auto_scaling_group = event.get("autoScalingGroup")
    
    try:
        # Get existing schedule to find current scheduled actions
        existing_arns = get_existing_scheduled_action_arns(model_id)
        
        # Delete existing scheduled actions
        if existing_arns:
            delete_scheduled_actions(existing_arns)
            logger.info(f"Deleted {len(existing_arns)} existing scheduled actions for model {model_id}")
        
        scheduled_action_arns = []
        schedule_enabled = False
        
        # Create new scheduled actions if schedule is provided
        if schedule_config and auto_scaling_group:
            scheduling_config = SchedulingConfig(**schedule_config)
            scheduled_action_arns = create_scheduled_actions(
                model_id=model_id,
                auto_scaling_group=auto_scaling_group,
                schedule_config=scheduling_config
            )
            schedule_enabled = True
            logger.info(f"Created {len(scheduled_action_arns)} new scheduled actions for model {model_id}")
        else:
            # If no schedule config provided, disable scheduling
            scheduling_config = SchedulingConfig(scheduleType=ScheduleType.NONE)
        
        # Update model record
        update_model_schedule_record(
            model_id=model_id,
            scheduling_config=scheduling_config,
            scheduled_action_arns=scheduled_action_arns,
            enabled=schedule_enabled
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Schedule updated successfully",
                "modelId": model_id,
                "scheduledActionArns": scheduled_action_arns,
                "scheduleEnabled": schedule_enabled
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to update schedule for model {model_id}: {str(e)}")
        raise ScheduleManagementError(f"Failed to update schedule: {str(e)}")


def delete_schedule(event: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a schedule for a model"""
    model_id = event["modelId"]
    
    try:
        # Get existing scheduled actions
        existing_arns = get_existing_scheduled_action_arns(model_id)
        
        # Delete scheduled actions
        if existing_arns:
            delete_scheduled_actions(existing_arns)
            logger.info(f"Deleted {len(existing_arns)} scheduled actions for model {model_id}")
        
        # Update model record to disable scheduling
        scheduling_config = SchedulingConfig(scheduleType=ScheduleType.NONE)
        update_model_schedule_record(
            model_id=model_id,
            scheduling_config=scheduling_config,
            scheduled_action_arns=[],
            enabled=False
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Schedule deleted successfully",
                "modelId": model_id,
                "scheduleEnabled": False
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to delete schedule for model {model_id}: {str(e)}")
        raise ScheduleManagementError(f"Failed to delete schedule: {str(e)}")


def get_schedule(event: Dict[str, Any]) -> Dict[str, Any]:
    """Get current schedule configuration for a model"""
    model_id = event["modelId"]
    
    try:
        # Get model record from DynamoDB
        response = model_table.get_item(Key={"model_id": model_id})
        
        if "Item" not in response:
            raise ValueError(f"Model {model_id} not found")
        
        model_item = response["Item"]
        auto_scaling_config = model_item.get("autoScalingConfig", {})
        scheduling_config = auto_scaling_config.get("scheduling", {})
        
        # Calculate next scheduled action if schedule is active
        next_action = None
        if scheduling_config.get("scheduleEnabled", False):
            next_action = calculate_next_scheduled_action(scheduling_config)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "modelId": model_id,
                "scheduling": scheduling_config,
                "nextScheduledAction": next_action
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"Failed to get schedule for model {model_id}: {str(e)}")
        raise ScheduleManagementError(f"Failed to get schedule: {str(e)}")


def create_scheduled_actions(
    model_id: str,
    auto_scaling_group: str,
    schedule_config: SchedulingConfig
) -> List[str]:
    """Create Auto Scaling scheduled actions based on schedule configuration"""
    scheduled_action_arns = []
    
    if schedule_config.scheduleType == ScheduleType.RECURRING_DAILY:
        # Create daily recurring schedule
        if not schedule_config.dailySchedule:
            raise ValueError("dailySchedule required for RECURRING_DAILY type")
        
        scheduled_action_arns.extend(
            create_daily_scheduled_actions(
                model_id, auto_scaling_group, schedule_config.dailySchedule, schedule_config.timezone
            )
        )
        
    elif schedule_config.scheduleType == ScheduleType.WEEKDAYS_ONLY:
        # Create weekdays-only schedule
        if not schedule_config.dailySchedule:
            raise ValueError("dailySchedule required for WEEKDAYS_ONLY type")
        
        scheduled_action_arns.extend(
            create_weekdays_scheduled_actions(
                model_id, auto_scaling_group, schedule_config.dailySchedule, schedule_config.timezone
            )
        )
        
    elif schedule_config.scheduleType == ScheduleType.EACH_DAY:
        # Create individual day schedules
        if not schedule_config.weeklySchedule:
            raise ValueError("weeklySchedule required for EACH_DAY type")
        
        scheduled_action_arns.extend(
            create_weekly_scheduled_actions(
                model_id, auto_scaling_group, schedule_config.weeklySchedule, schedule_config.timezone
            )
        )
    
    return scheduled_action_arns


def get_capacity_config(model_id: str, auto_scaling_group: str) -> Dict[str, int]:
    """Get capacity configuration from model record or fallback to existing ASG configuration"""
    try:
        # First, try to get capacity from the model's AutoScalingConfig
        response = model_table.get_item(Key={"model_id": model_id})
        
        if "Item" in response:
            model_item = response["Item"]
            auto_scaling_config = model_item.get("autoScalingConfig", {})
            
            if auto_scaling_config:
                min_capacity = auto_scaling_config.get("minCapacity")
                max_capacity = auto_scaling_config.get("maxCapacity")
                desired_capacity = min_capacity
                
                if min_capacity is not None and max_capacity is not None:
                    logger.info(f"Using model AutoScalingConfig for {model_id}: min={min_capacity}, max={max_capacity}, desired={desired_capacity}")
                    return {
                        "MinSize": min_capacity,
                        "MaxSize": max_capacity,
                        "DesiredCapacity": desired_capacity
                    }
        
        # Fallback: try to get from existing ASG if model config is not available
        logger.info(f"Model AutoScalingConfig not found for {model_id}, falling back to existing ASG configuration")
        response = autoscaling_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[auto_scaling_group]
        )
        
        if not response['AutoScalingGroups']:
            # If ASG doesn't exist either, use reasonable defaults
            logger.warning(f"Auto Scaling Group {auto_scaling_group} not found, using default capacity values")
            return {
                "MinSize": 1,
                "MaxSize": 1,
                "DesiredCapacity": 1
            }
        
        asg = response['AutoScalingGroups'][0]
        logger.info(f"Using existing ASG configuration for {auto_scaling_group}")
        
        return {
            "MinSize": asg['MinSize'],
            "MaxSize": asg['MaxSize'],
            "DesiredCapacity": asg['DesiredCapacity']
        }
        
    except ClientError as e:
        logger.error(f"Failed to get capacity configuration for model {model_id}: {e}")
        raise ScheduleManagementError(f"Failed to get capacity configuration: {str(e)}")


def create_daily_scheduled_actions(
    model_id: str,
    auto_scaling_group: str,
    day_schedule: DaySchedule,
    timezone_name: str
) -> List[str]:
    """Create scheduled actions for daily recurring schedule"""
    scheduled_action_arns = []
    
    # Get capacity configuration from model record or fallback to existing ASG
    capacity_config = get_capacity_config(model_id, auto_scaling_group)
    
    # Create start action
    start_cron = convert_to_utc_cron(day_schedule.startTime, timezone_name)
    start_action_name = f"{model_id}-daily-start"
    
    try:
        autoscaling_client.put_scheduled_update_group_action(
            AutoScalingGroupName=auto_scaling_group,
            ScheduledActionName=start_action_name,
            Recurrence=start_cron,
            MinSize=capacity_config["MinSize"],
            MaxSize=capacity_config["MaxSize"],
            DesiredCapacity=capacity_config["DesiredCapacity"]
        )
        
        start_arn = construct_scheduled_action_arn(auto_scaling_group, start_action_name)
        scheduled_action_arns.append(start_arn)
        logger.info(f"Created daily start action: {start_action_name}")
        
    except ClientError as e:
        logger.error(f"Failed to create start action {start_action_name}: {e}")
        raise
    
    # Create stop action
    stop_cron = convert_to_utc_cron(day_schedule.stopTime, timezone_name)
    stop_action_name = f"{model_id}-daily-stop"
    
    try:
        autoscaling_client.put_scheduled_update_group_action(
            AutoScalingGroupName=auto_scaling_group,
            ScheduledActionName=stop_action_name,
            Recurrence=stop_cron,
            MinSize=0,
            MaxSize=0,
            DesiredCapacity=0
        )
        
        stop_arn = construct_scheduled_action_arn(auto_scaling_group, stop_action_name)
        scheduled_action_arns.append(stop_arn)
        logger.info(f"Created daily stop action: {stop_action_name}")
        
    except ClientError as e:
        logger.error(f"Failed to create stop action {stop_action_name}: {e}")
        # Clean up start action if stop action fails
        try:
            autoscaling_client.delete_scheduled_action(
                AutoScalingGroupName=auto_scaling_group,
                ScheduledActionName=start_action_name
            )
        except Exception:
            pass
        raise
    
    return scheduled_action_arns


def create_weekdays_scheduled_actions(
    model_id: str,
    auto_scaling_group: str,
    day_schedule: DaySchedule,
    timezone_name: str
) -> List[str]:
    """Create scheduled actions for weekdays-only schedule"""
    scheduled_action_arns = []
    
    # Get capacity configuration from model record or fallback to existing ASG
    capacity_config = get_capacity_config(model_id, auto_scaling_group)
    
    # Create start action (Monday-Friday)
    start_cron = convert_to_utc_cron_weekdays(day_schedule.startTime, timezone_name)
    start_action_name = f"{model_id}-weekdays-start"
    
    try:
        autoscaling_client.put_scheduled_update_group_action(
            AutoScalingGroupName=auto_scaling_group,
            ScheduledActionName=start_action_name,
            Recurrence=start_cron,
            MinSize=capacity_config["MinSize"],
            MaxSize=capacity_config["MaxSize"],
            DesiredCapacity=capacity_config["DesiredCapacity"]
        )
        
        start_arn = construct_scheduled_action_arn(auto_scaling_group, start_action_name)
        scheduled_action_arns.append(start_arn)
        logger.info(f"Created weekdays start action: {start_action_name}")
        
    except ClientError as e:
        logger.error(f"Failed to create weekdays start action {start_action_name}: {e}")
        raise
    
    # Create stop action (Monday-Friday)
    stop_cron = convert_to_utc_cron_weekdays(day_schedule.stopTime, timezone_name)
    stop_action_name = f"{model_id}-weekdays-stop"
    
    try:
        autoscaling_client.put_scheduled_update_group_action(
            AutoScalingGroupName=auto_scaling_group,
            ScheduledActionName=stop_action_name,
            Recurrence=stop_cron,
            MinSize=0,
            MaxSize=0,
            DesiredCapacity=0
        )
        
        stop_arn = construct_scheduled_action_arn(auto_scaling_group, stop_action_name)
        scheduled_action_arns.append(stop_arn)
        logger.info(f"Created weekdays stop action: {stop_action_name}")
        
    except ClientError as e:
        logger.error(f"Failed to create weekdays stop action {stop_action_name}: {e}")
        # Clean up start action if stop action fails
        try:
            autoscaling_client.delete_scheduled_action(
                AutoScalingGroupName=auto_scaling_group,
                ScheduledActionName=start_action_name
            )
        except Exception:
            pass
        raise
    
    return scheduled_action_arns


def create_weekly_scheduled_actions(
    model_id: str,
    auto_scaling_group: str,
    weekly_schedule: WeeklySchedule,
    timezone_name: str
) -> List[str]:
    """Create scheduled actions for weekly schedule (different times each day with support for multiple periods)"""
    scheduled_action_arns = []
    
    # Get capacity configuration from model record or fallback to existing ASG
    capacity_config = get_capacity_config(model_id, auto_scaling_group)
    
    day_mapping = {
        'monday': (1, weekly_schedule.monday),
        'tuesday': (2, weekly_schedule.tuesday),
        'wednesday': (3, weekly_schedule.wednesday),
        'thursday': (4, weekly_schedule.thursday),
        'friday': (5, weekly_schedule.friday),
        'saturday': (6, weekly_schedule.saturday),
        'sunday': (0, weekly_schedule.sunday)
    }
    
    for day_name, (day_num, day_schedules) in day_mapping.items():
        if not day_schedules:
            continue
        
        # Handle multiple time periods for each day
        for period_idx, day_schedule in enumerate(day_schedules):
            # Create start action for this period
            start_cron = convert_to_utc_cron_with_day(day_schedule.startTime, timezone_name, day_num)
            start_action_name = f"{model_id}-{day_name}-period{period_idx + 1}-start"
            
            try:
                autoscaling_client.put_scheduled_update_group_action(
                    AutoScalingGroupName=auto_scaling_group,
                    ScheduledActionName=start_action_name,
                    Recurrence=start_cron,
                    MinSize=capacity_config["MinSize"],
                    MaxSize=capacity_config["MaxSize"],
                    DesiredCapacity=capacity_config["DesiredCapacity"]
                )
                
                start_arn = construct_scheduled_action_arn(auto_scaling_group, start_action_name)
                scheduled_action_arns.append(start_arn)
                logger.info(f"Created {day_name} period {period_idx + 1} start action: {start_action_name}")
                
            except ClientError as e:
                logger.error(f"Failed to create {day_name} period {period_idx + 1} start action {start_action_name}: {e}")
                cleanup_scheduled_actions(scheduled_action_arns)
                raise
            
            # Create stop action for this period
            stop_cron = convert_to_utc_cron_with_day(day_schedule.stopTime, timezone_name, day_num)
            stop_action_name = f"{model_id}-{day_name}-period{period_idx + 1}-stop"
            
            try:
                autoscaling_client.put_scheduled_update_group_action(
                    AutoScalingGroupName=auto_scaling_group,
                    ScheduledActionName=stop_action_name,
                    Recurrence=stop_cron,
                    MinSize=0,
                    MaxSize=0,
                    DesiredCapacity=0
                )
                
                stop_arn = construct_scheduled_action_arn(auto_scaling_group, stop_action_name)
                scheduled_action_arns.append(stop_arn)
                logger.info(f"Created {day_name} period {period_idx + 1} stop action: {stop_action_name}")
                
            except ClientError as e:
                logger.error(f"Failed to create {day_name} period {period_idx + 1} stop action {stop_action_name}: {e}")
                cleanup_scheduled_actions(scheduled_action_arns)
                raise
    
    return scheduled_action_arns


def convert_to_utc_cron(time_str: str, timezone_name: str) -> str:
    """Convert local time to UTC cron expression"""
    from zoneinfo import ZoneInfo
    
    # Parse time
    hour, minute = map(int, time_str.split(':'))
    
    # Create timezone-aware datetime for today
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    local_dt = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute), tzinfo=tz)
    
    # Convert to UTC
    utc_dt = local_dt.astimezone(dt_timezone.utc)
    
    # Return cron expression (minute hour * * *)
    return f"{utc_dt.minute} {utc_dt.hour} * * *"


def convert_to_utc_cron_weekdays(time_str: str, timezone_name: str) -> str:
    """Convert local time to UTC cron expression for weekdays only (Mon-Fri)"""
    from zoneinfo import ZoneInfo
    
    # Parse time
    hour, minute = map(int, time_str.split(':'))
    
    # Create timezone-aware datetime
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    local_dt = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute), tzinfo=tz)
    
    # Convert to UTC
    utc_dt = local_dt.astimezone(dt_timezone.utc)
    
    # Return cron expression with weekdays (minute hour * * 1-5)
    return f"{utc_dt.minute} {utc_dt.hour} * * 1-5"


def convert_to_utc_cron_with_day(time_str: str, timezone_name: str, day_of_week: int) -> str:
    """Convert local time to UTC cron expression with specific day of week"""
    from zoneinfo import ZoneInfo
    
    # Parse time
    hour, minute = map(int, time_str.split(':'))
    
    # Create timezone-aware datetime
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    local_dt = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute), tzinfo=tz)
    
    # Convert to UTC
    utc_dt = local_dt.astimezone(dt_timezone.utc)
    
    # Return cron expression with day of week (minute hour * * day)
    return f"{utc_dt.minute} {utc_dt.hour} * * {day_of_week}"


def construct_scheduled_action_arn(auto_scaling_group: str, action_name: str) -> str:
    """Construct ARN for a scheduled action"""
    region = os.environ.get("AWS_REGION", "us-east-1")
    account_id = os.environ.get("AWS_ACCOUNT_ID")
    
    if not account_id:
        # Try to get account ID from STS if not in environment
        try:
            sts_client = boto3.client("sts")
            account_id = sts_client.get_caller_identity()["Account"]
        except Exception:
            raise ValueError("Unable to determine AWS Account ID")
    
    return (
        f"arn:aws:autoscaling:{region}:{account_id}:scheduledUpdateGroupAction:*:"
        f"autoScalingGroupName/{auto_scaling_group}:scheduledActionName/{action_name}"
    )


def delete_scheduled_actions(scheduled_action_arns: List[str]) -> None:
    """Delete Auto Scaling scheduled actions by ARN"""
    for arn in scheduled_action_arns:
        try:
            # Extract action name and ASG name from ARN
            action_name = arn.split(':scheduledActionName/')[-1]
            asg_name = arn.split(':autoScalingGroupName/')[-1].split(':')[0]
            
            autoscaling_client.delete_scheduled_action(
                AutoScalingGroupName=asg_name,
                ScheduledActionName=action_name
            )
            logger.info(f"Deleted scheduled action: {action_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                logger.warning(f"Scheduled action {action_name} not found (may already be deleted)")
            else:
                logger.error(f"Failed to delete scheduled action {action_name}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error deleting scheduled action {action_name}: {e}")
            raise


def cleanup_scheduled_actions(scheduled_action_arns: List[str]) -> None:
    """Clean up scheduled actions (used for error recovery)"""
    for arn in scheduled_action_arns:
        try:
            action_name = arn.split(':scheduledActionName/')[-1]
            asg_name = arn.split(':autoScalingGroupName/')[-1].split(':')[0]
            
            autoscaling_client.delete_scheduled_action(
                AutoScalingGroupName=asg_name,
                ScheduledActionName=action_name
            )
        except Exception:
            # Ignore errors during cleanup
            pass


def get_existing_scheduled_action_arns(model_id: str) -> List[str]:
    """Get existing scheduled action ARNs for a model"""
    try:
        response = model_table.get_item(Key={"model_id": model_id})
        
        if "Item" not in response:
            return []
        
        model_item = response["Item"]
        auto_scaling_config = model_item.get("autoScalingConfig", {})
        scheduling_config = auto_scaling_config.get("scheduling", {})
        
        return scheduling_config.get("scheduledActionArns", [])
        
    except Exception as e:
        logger.error(f"Failed to get existing scheduled actions for model {model_id}: {e}")
        return []


def update_model_schedule_record(
    model_id: str,
    scheduling_config: SchedulingConfig,
    scheduled_action_arns: List[str],
    enabled: bool
) -> None:
    """Update model record in DynamoDB with schedule information"""
    try:
        # Prepare the scheduling configuration for storage
        schedule_data = scheduling_config.model_dump()
        schedule_data["scheduledActionArns"] = scheduled_action_arns
        schedule_data["scheduleEnabled"] = enabled
        schedule_data["lastScheduleUpdate"] = datetime.now(dt_timezone.utc).isoformat()
        
        # Use boolean flags instead of scheduleStatus enum
        schedule_data["scheduleConfigured"] = enabled
        schedule_data["lastScheduleFailed"] = False  # Reset failure flag on successful update
        
        # Calculate next scheduled action
        if enabled:
            next_action = calculate_next_scheduled_action(schedule_data)
            if next_action:
                schedule_data["nextScheduledAction"] = next_action
        
        # Update the model record
        model_table.update_item(
            Key={"model_id": model_id},
            UpdateExpression="SET autoScalingConfig.scheduling = :scheduling",
            ExpressionAttributeValues={
                ":scheduling": schedule_data
            }
        )
        
        logger.info(f"Updated schedule record for model {model_id}")
        
    except Exception as e:
        logger.error(f"Failed to update schedule record for model {model_id}: {e}")
        raise


def calculate_next_scheduled_action(schedule_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Calculate the next scheduled action for a model."""
    try:
        schedule_type = schedule_data.get("scheduleType")
        
        if schedule_type == ScheduleType.NONE:
            return None
        
        # For now, return a placeholder - this would be implemented with more complex logic
        # to calculate the actual next action based on current time and schedule configuration
        return {
            "action": "START",
            "scheduledTime": datetime.now(dt_timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate next scheduled action: {e}")
        return None
