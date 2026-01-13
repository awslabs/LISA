#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from models.domain_objects import (
    DailySchedulingConfig,
    DaySchedule,
    RecurringSchedulingConfig,
    ScheduleType,
    SchedulingConfig,
    WeeklySchedule,
)
from models.exception import ModelNotFoundError
from utilities.time import iso_string

logger = logging.getLogger(__name__)

retry_config = Config(
    region_name=os.environ.get("AWS_REGION", "us-east-1"), retries={"max_attempts": 3, "mode": "adaptive"}
)
autoscaling_client = boto3.client("autoscaling", config=retry_config)
dynamodb = boto3.resource("dynamodb", config=retry_config)
model_table = dynamodb.Table(os.environ.get("MODEL_TABLE_NAME"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Main Lambda handler for schedule management operations"""
    try:
        logger.info(f"Processing schedule management request: {json.dumps(event, default=str)}")

        # Extract operation and parameters
        operation = event.get("operation")
        model_id = event.get("modelId")

        if not operation or not model_id:
            raise ValueError("Both 'operation' and 'modelId' are required")

        # Route to appropriate handler
        if operation == "update":
            return update_schedule(event)
        elif operation == "delete":
            return delete_schedule(event)
        elif operation == "get":
            return get_schedule(event)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    except Exception as e:
        logger.error(f"Schedule management error: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": "ScheduleManagementError", "message": str(e)})}


def update_schedule(event: dict[str, Any]) -> dict[str, Any]:
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
            full_schedule_data = merge_schedule_data(model_id, schedule_config)
            scheduling_config = create_scheduling_config(full_schedule_data)
            scheduled_action_arns = create_scheduled_actions(
                model_id=model_id, auto_scaling_group=auto_scaling_group, schedule_config=scheduling_config
            )
            schedule_enabled = True
            logger.info(f"Created {len(scheduled_action_arns)} new scheduled actions for model {model_id}")
        else:
            # If no schedule config provided, disable scheduling
            scheduling_config = None

        # Update model record
        update_model_schedule_record(
            model_id=model_id,
            scheduling_config=scheduling_config,
            scheduled_action_arns=scheduled_action_arns,
            enabled=schedule_enabled,
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Schedule updated successfully",
                    "modelId": model_id,
                    "scheduledActionArns": scheduled_action_arns,
                    "scheduleEnabled": schedule_enabled,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Failed to update schedule for model {model_id}: {str(e)}")
        raise RuntimeError(f"Failed to update schedule: {str(e)}")


def delete_schedule(event: dict[str, Any]) -> dict[str, Any]:
    """Delete a schedule for a model"""
    model_id = event["modelId"]

    try:
        # Get model info to find the Auto Scaling Group
        response = model_table.get_item(Key={"model_id": model_id})
        if "Item" not in response:
            raise ModelNotFoundError(f"Model {model_id} not found")

        model_item = response["Item"]
        auto_scaling_group = model_item.get("auto_scaling_group")

        # Get existing scheduled actions from DDB
        existing_arns = get_existing_scheduled_action_arns(model_id)

        # Delete scheduled actions by ARN if we have them
        if existing_arns:
            delete_scheduled_actions(existing_arns)
            logger.info(f"Deleted {len(existing_arns)} scheduled actions for model {model_id} using stored ARNs")

        # Double clean -- clean up by name pattern to ensure we don't leave any orphaned actions
        if auto_scaling_group:
            cleanup_scheduled_actions_by_name_pattern(auto_scaling_group, model_id)

        # Update model record to disable scheduling
        update_model_schedule_record(model_id=model_id, scheduling_config=None, scheduled_action_arns=[], enabled=False)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Schedule deleted successfully", "modelId": model_id, "scheduleEnabled": False}
            ),
        }

    except Exception as e:
        logger.error(f"Failed to delete schedule for model {model_id}: {str(e)}")
        raise RuntimeError(f"Failed to delete schedule: {str(e)}")


def get_schedule(event: dict[str, Any]) -> dict[str, Any]:
    """Get current schedule configuration for a model"""
    model_id = event["modelId"]

    try:
        # Get model record from DynamoDB
        response = model_table.get_item(Key={"model_id": model_id})

        if "Item" not in response:
            raise ModelNotFoundError(f"Model {model_id} not found")

        model_item = response["Item"]
        model_config = model_item.get("model_config", {})
        auto_scaling_config = model_config.get("autoScalingConfig", {})
        scheduling_config = auto_scaling_config.get("scheduling", {})

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "modelId": model_id,
                    "scheduling": scheduling_config,
                    "nextScheduledAction": scheduling_config.get("nextScheduledAction"),
                },
                default=str,
            ),
        }

    except Exception as e:
        logger.error(f"Failed to get schedule for model {model_id}: {str(e)}")
        raise RuntimeError(f"Failed to get schedule: {str(e)}")


def create_scheduled_actions(model_id: str, auto_scaling_group: str, schedule_config: SchedulingConfig) -> list[str]:
    """Create Auto Scaling scheduled actions based on schedule configuration"""
    scheduled_action_arns = []

    if schedule_config.scheduleType == ScheduleType.RECURRING:
        # Create daily recurring schedule
        scheduled_action_arns.extend(
            create_recurring_scheduled_actions(
                model_id, auto_scaling_group, schedule_config.recurringSchedule, schedule_config.timezone
            )
        )

    elif schedule_config.scheduleType == ScheduleType.DAILY:
        # Create individual day schedules
        scheduled_action_arns.extend(
            create_daily_scheduled_actions(
                model_id, auto_scaling_group, schedule_config.dailySchedule, schedule_config.timezone
            )
        )

    return scheduled_action_arns


def create_scheduling_config(schedule_data: dict[str, Any]) -> SchedulingConfig:
    """Create the appropriate scheduling config instance based on scheduleType"""
    schedule_type = schedule_data.get("scheduleType")

    if schedule_type == ScheduleType.DAILY:
        return DailySchedulingConfig(**schedule_data)
    elif schedule_type == ScheduleType.RECURRING:
        return RecurringSchedulingConfig(**schedule_data)
    else:
        raise ValueError(f"Unknown schedule type: {schedule_type}")


def get_existing_asg_capacity(auto_scaling_group: str) -> dict[str, int]:
    """Get the existing Auto Scaling Group's current capacity configuration"""
    try:
        response = autoscaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[auto_scaling_group])

        if not response["AutoScalingGroups"]:
            raise ValueError(f"Auto Scaling Group {auto_scaling_group} not found")

        asg = response["AutoScalingGroups"][0]
        logger.info(
            f"Using existing ASG capacity for {auto_scaling_group}: min={asg['MinSize']}, max={asg['MaxSize']}, "
            f"desired={asg['DesiredCapacity']}"
        )

        return {"MinSize": asg["MinSize"], "MaxSize": asg["MaxSize"], "DesiredCapacity": asg["DesiredCapacity"]}

    except ClientError as e:
        logger.error(f"Failed to get ASG capacity for {auto_scaling_group}: {e}")
        raise RuntimeError(f"Failed to get ASG capacity: {str(e)}")


def get_model_baseline_capacity(model_id: str) -> dict[str, int]:
    """Get the baseline capacity configuration from the model's DynamoDB record"""
    try:
        response = model_table.get_item(Key={"model_id": model_id})

        if "Item" not in response:
            raise ModelNotFoundError(f"Model {model_id} not found in DynamoDB")

        model_item = response["Item"]
        model_config = model_item.get("model_config", {})
        auto_scaling_config = model_config.get("autoScalingConfig", {})

        # Get baseline capacity from model configuration
        min_capacity = int(auto_scaling_config.get("minCapacity", 1))
        max_capacity = int(auto_scaling_config.get("maxCapacity", 1))
        desired_capacity = auto_scaling_config.get("desiredCapacity", 1)

        # If desired capacity is not set, use min capacity as default
        if desired_capacity is None:
            desired_capacity = min_capacity
        else:
            desired_capacity = int(desired_capacity)

        logger.info(
            f"Using baseline model capacity for {model_id}: min={min_capacity}, max={max_capacity}, "
            f"desired={desired_capacity}"
        )

        return {"MinSize": min_capacity, "MaxSize": max_capacity, "DesiredCapacity": desired_capacity}

    except Exception as e:
        logger.error(f"Failed to get baseline capacity for model {model_id}: {e}")
        raise RuntimeError(f"Failed to get baseline capacity: {str(e)}")


def check_daily_immediate_scaling(
    auto_scaling_group: str, daily_schedule: WeeklySchedule, timezone_name: str, model_id: str
) -> None:
    """Check current day and time, scale ASG down to 0 if outside scheduled window for daily schedules"""
    try:
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz)
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Map Python weekday to our schedule
        day_schedules = {
            0: daily_schedule.monday,  # Monday
            1: daily_schedule.tuesday,  # Tuesday
            2: daily_schedule.wednesday,  # Wednesday
            3: daily_schedule.thursday,  # Thursday
            4: daily_schedule.friday,  # Friday
            5: daily_schedule.saturday,  # Saturday
            6: daily_schedule.sunday,  # Sunday
        }

        today_schedule = day_schedules.get(current_weekday)

        if today_schedule:
            # There's a schedule for today, check if we're within the time window
            scale_immediately(auto_scaling_group, today_schedule, timezone_name, model_id)
        else:
            # No schedule for today, scale down to 0
            logger.info(f"No schedule defined for today ({now.strftime('%A')}). Scaling down to 0 instances.")

            autoscaling_client.update_auto_scaling_group(
                AutoScalingGroupName=auto_scaling_group, MinSize=0, MaxSize=0, DesiredCapacity=0
            )

            logger.info(f"Successfully scaled down ASG {auto_scaling_group} to 0 instances (no schedule today)")

    except Exception as e:
        logger.error(f"Failed to check daily immediate scaling for ASG {auto_scaling_group}: {e}")


def scale_immediately(auto_scaling_group: str, day_schedule: DaySchedule, timezone_name: str, model_id: str) -> None:
    """Check current time and immediately scale ASG up or down based on scheduled window"""
    try:
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz)
        current_time = now.time()

        # Parse schedule times
        start_hour, start_minute = map(int, day_schedule.startTime.split(":"))
        stop_hour, stop_minute = map(int, day_schedule.stopTime.split(":"))

        start_time_obj = datetime.min.time().replace(hour=start_hour, minute=start_minute)
        stop_time_obj = datetime.min.time().replace(hour=stop_hour, minute=stop_minute)

        # Simple 24-hour window check
        is_within_window = start_time_obj <= current_time <= stop_time_obj

        if not is_within_window:
            logger.info(
                f"Current time {current_time} is outside scheduled window "
                f"({day_schedule.startTime} - {day_schedule.stopTime}). Scaling down to 0 instances."
            )

            # Scale down immediately
            autoscaling_client.update_auto_scaling_group(
                AutoScalingGroupName=auto_scaling_group, MinSize=0, MaxSize=0, DesiredCapacity=0
            )

            logger.info(f"Successfully scaled down ASG {auto_scaling_group} to 0 instances")
        else:
            # Get current ASG state
            current_desired = get_existing_asg_capacity(auto_scaling_group)["DesiredCapacity"]

            # Within scheduled window - check if we need to scale up
            if current_desired == 0:
                capacity_config = get_model_baseline_capacity(model_id)

                logger.info(
                    f"Current time {current_time} is within scheduled window "
                    f"({day_schedule.startTime} - {day_schedule.stopTime}). Scaling up from 0."
                )

                autoscaling_client.update_auto_scaling_group(
                    AutoScalingGroupName=auto_scaling_group,
                    MinSize=int(capacity_config["MinSize"]),
                    MaxSize=int(capacity_config["MaxSize"]),
                    DesiredCapacity=int(capacity_config["DesiredCapacity"]),
                )

                logger.info(f"Successfully scaled up ASG {auto_scaling_group}")
            else:
                logger.info(
                    f"Current time {current_time} is within scheduled window "
                    f"({day_schedule.startTime} - {day_schedule.stopTime}). "
                    f"ASG already running (desired={current_desired})."
                )

    except Exception as e:
        logger.error(f"Failed to check/apply immediate scaling for ASG {auto_scaling_group}: {e}")


def create_recurring_scheduled_actions(
    model_id: str, auto_scaling_group: str, day_schedule: DaySchedule, timezone_name: str
) -> list[str]:
    """Create scheduled actions for recurring schedule"""
    scheduled_action_arns = []

    # Get baseline capacity config from model DDB record
    capacity_config = get_model_baseline_capacity(model_id)

    # Create start action
    start_cron = time_to_cron(day_schedule.startTime)
    start_action_name = f"{model_id}-daily-start"

    try:
        autoscaling_client.put_scheduled_update_group_action(
            AutoScalingGroupName=auto_scaling_group,
            ScheduledActionName=start_action_name,
            Recurrence=start_cron,
            TimeZone=timezone_name,
            MinSize=capacity_config["MinSize"],
            MaxSize=capacity_config["MaxSize"],
            DesiredCapacity=capacity_config["DesiredCapacity"],
        )

        start_arn = construct_scheduled_action_arn(auto_scaling_group, start_action_name)
        scheduled_action_arns.append(start_arn)
        logger.info(f"Created daily start action: {start_action_name}")

    except ClientError as e:
        logger.error(f"Failed to create start action {start_action_name}: {e}")
        raise

    # Create stop action
    stop_cron = time_to_cron(day_schedule.stopTime)
    stop_action_name = f"{model_id}-daily-stop"

    try:
        autoscaling_client.put_scheduled_update_group_action(
            AutoScalingGroupName=auto_scaling_group,
            ScheduledActionName=stop_action_name,
            Recurrence=stop_cron,
            TimeZone=timezone_name,
            MinSize=0,
            MaxSize=0,
            DesiredCapacity=0,
        )

        stop_arn = construct_scheduled_action_arn(auto_scaling_group, stop_action_name)
        scheduled_action_arns.append(stop_arn)
        logger.info(f"Created daily stop action: {stop_action_name}")

    except ClientError as e:
        logger.error(f"Failed to create stop action {stop_action_name}: {e}")
        # Clean up start action if stop action fails
        try:
            autoscaling_client.delete_scheduled_action(
                AutoScalingGroupName=auto_scaling_group, ScheduledActionName=start_action_name
            )
        except Exception:
            pass  # nosec B110
        raise

    # Check current time and scale immediately if outside scheduled window
    scale_immediately(auto_scaling_group, day_schedule, timezone_name, model_id)

    return scheduled_action_arns


def create_daily_scheduled_actions(
    model_id: str, auto_scaling_group: str, daily_schedule: WeeklySchedule, timezone_name: str
) -> list[str]:
    """Create scheduled actions for daily schedule (different times each day with one start/stop time per day)"""
    scheduled_action_arns = []

    # Get baseline capacity config from DDB record
    capacity_config = get_model_baseline_capacity(model_id)

    day_mapping = {
        "monday": (1, daily_schedule.monday),
        "tuesday": (2, daily_schedule.tuesday),
        "wednesday": (3, daily_schedule.wednesday),
        "thursday": (4, daily_schedule.thursday),
        "friday": (5, daily_schedule.friday),
        "saturday": (6, daily_schedule.saturday),
        "sunday": (0, daily_schedule.sunday),
    }

    for day_name, (day_num, day_schedule) in day_mapping.items():
        if not day_schedule:
            continue

        # Create start action for this day
        start_cron = time_to_cron_with_day(day_schedule.startTime, day_num)
        start_action_name = f"{model_id}-{day_name}-start"

        try:
            autoscaling_client.put_scheduled_update_group_action(
                AutoScalingGroupName=auto_scaling_group,
                ScheduledActionName=start_action_name,
                Recurrence=start_cron,
                TimeZone=timezone_name,
                MinSize=capacity_config["MinSize"],
                MaxSize=capacity_config["MaxSize"],
                DesiredCapacity=capacity_config["DesiredCapacity"],
            )

            start_arn = construct_scheduled_action_arn(auto_scaling_group, start_action_name)
            scheduled_action_arns.append(start_arn)
            logger.info(f"Created {day_name} start action: {start_action_name}")

        except ClientError as e:
            logger.error(f"Failed to create {day_name} start action {start_action_name}: {e}")
            cleanup_scheduled_actions(scheduled_action_arns)
            raise

        # Create stop action for this day
        stop_cron = time_to_cron_with_day(day_schedule.stopTime, day_num)
        stop_action_name = f"{model_id}-{day_name}-stop"

        try:
            autoscaling_client.put_scheduled_update_group_action(
                AutoScalingGroupName=auto_scaling_group,
                ScheduledActionName=stop_action_name,
                Recurrence=stop_cron,
                TimeZone=timezone_name,
                MinSize=0,
                MaxSize=0,
                DesiredCapacity=0,
            )

            stop_arn = construct_scheduled_action_arn(auto_scaling_group, stop_action_name)
            scheduled_action_arns.append(stop_arn)
            logger.info(f"Created {day_name} stop action: {stop_action_name}")

        except ClientError as e:
            logger.error(f"Failed to create {day_name} stop action {stop_action_name}: {e}")
            cleanup_scheduled_actions(scheduled_action_arns)
            raise

    # Check current time and scale immediately
    check_daily_immediate_scaling(auto_scaling_group, daily_schedule, timezone_name, model_id)

    return scheduled_action_arns


def time_to_cron(time_str: str) -> str:
    """Convert time string (HH:MM) to cron expression"""
    hour, minute = map(int, time_str.split(":"))
    return f"{minute} {hour} * * *"


def time_to_cron_with_day(time_str: str, day_of_week: int) -> str:
    """Convert time string (HH:MM) to cron expression with day"""
    hour, minute = map(int, time_str.split(":"))
    return f"{minute} {hour} * * {day_of_week}"


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


def delete_scheduled_actions(scheduled_action_arns: list[str]) -> None:
    """Delete Auto Scaling scheduled actions by ARN"""
    for arn in scheduled_action_arns:
        try:
            # Extract action name and ASG name from ARN
            action_name = arn.split(":scheduledActionName/")[-1]
            asg_name = arn.split(":autoScalingGroupName/")[-1].split(":")[0]

            autoscaling_client.delete_scheduled_action(AutoScalingGroupName=asg_name, ScheduledActionName=action_name)
            logger.info(f"Deleted scheduled action: {action_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationError":
                logger.warning(f"Scheduled action {action_name} not found (may already be deleted)")
            else:
                logger.error(f"Failed to delete scheduled action {action_name}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error deleting scheduled action {action_name}: {e}")
            raise


def cleanup_scheduled_actions(scheduled_action_arns: list[str]) -> None:
    """Clean up scheduled actions (used for error recovery)"""
    for arn in scheduled_action_arns:
        try:
            action_name = arn.split(":scheduledActionName/")[-1]
            asg_name = arn.split(":autoScalingGroupName/")[-1].split(":")[0]

            autoscaling_client.delete_scheduled_action(AutoScalingGroupName=asg_name, ScheduledActionName=action_name)
        except Exception:
            # Ignore errors during cleanup
            pass  # nosec B110


def cleanup_scheduled_actions_by_name_pattern(auto_scaling_group: str, model_id: str) -> None:
    """Delete all scheduled actions for a model by finding them via name pattern"""
    try:
        # Get all scheduled actions for the Auto Scaling Group
        response = autoscaling_client.describe_scheduled_actions(AutoScalingGroupName=auto_scaling_group)

        scheduled_actions = response.get("ScheduledUpdateGroupActions", [])
        deleted_count = 0

        # Find actions that match our model naming pattern
        for action in scheduled_actions:
            action_name = action["ScheduledActionName"]

            # Check if this action belongs to our model using naming patterns:
            # {model_id}-daily-start, {model_id}-daily-stop
            # {model_id}-monday-start, {model_id}-tuesday-stop, etc.
            if (
                action_name.startswith(f"{model_id}-daily-")
                or action_name.startswith(f"{model_id}-monday-")
                or action_name.startswith(f"{model_id}-tuesday-")
                or action_name.startswith(f"{model_id}-wednesday-")
                or action_name.startswith(f"{model_id}-thursday-")
                or action_name.startswith(f"{model_id}-friday-")
                or action_name.startswith(f"{model_id}-saturday-")
                or action_name.startswith(f"{model_id}-sunday-")
            ):

                try:
                    autoscaling_client.delete_scheduled_action(
                        AutoScalingGroupName=auto_scaling_group, ScheduledActionName=action_name
                    )
                    deleted_count += 1
                    logger.info(f"Deleted scheduled action by pattern: {action_name}")

                except ClientError as e:
                    if e.response["Error"]["Code"] == "ValidationError":
                        logger.warning(f"Scheduled action {action_name} not found (may already be deleted)")
                    else:
                        logger.error(f"Failed to delete scheduled action {action_name}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error deleting scheduled action {action_name}: {e}")

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} scheduled actions for model {model_id} by name pattern")
        else:
            logger.info(f"No scheduled actions found for model {model_id} using name pattern cleanup")

    except ClientError as e:
        logger.error(f"Failed to describe scheduled actions for ASG {auto_scaling_group}: {e}")
    except Exception as e:
        logger.error(f"Failed to cleanup scheduled actions by pattern for model {model_id}: {e}")


def calculate_next_scheduled_action(schedule_config: SchedulingConfig, timezone_name: str) -> dict[str, str] | None:
    """Calculate the next scheduled action (START or STOP) based on the schedule configuration"""
    try:
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz)

        if schedule_config.scheduleType == ScheduleType.RECURRING:
            return _calculate_next_recurring_action(schedule_config.recurringSchedule, now, tz)
        elif schedule_config.scheduleType == ScheduleType.DAILY:
            return _calculate_next_daily_action(schedule_config.dailySchedule, now, tz)

        return None
    except Exception as e:
        logger.error(f"Failed to calculate next scheduled action: {e}")
        return None


def _calculate_next_recurring_action(day_schedule: DaySchedule, now: datetime, tz: ZoneInfo) -> dict[str, str]:
    """Calculate next action for recurring schedule"""
    # Parse schedule times
    start_hour, start_minute = map(int, day_schedule.startTime.split(":"))
    stop_hour, stop_minute = map(int, day_schedule.stopTime.split(":"))

    # Create time objects for today
    today = now.date()
    start_time = datetime.combine(today, datetime.min.time().replace(hour=start_hour, minute=start_minute)).replace(
        tzinfo=tz
    )
    stop_time = datetime.combine(today, datetime.min.time().replace(hour=stop_hour, minute=stop_minute)).replace(
        tzinfo=tz
    )

    # Check which action comes next
    if now < start_time:
        # Before start time today - next action is START today
        return {"action": "START", "scheduledTime": start_time.isoformat()}
    elif now < stop_time:
        # Between start and stop today - next action is STOP today
        return {"action": "STOP", "scheduledTime": stop_time.isoformat()}
    else:
        # After stop time today - next action is START tomorrow
        tomorrow_start = start_time + timedelta(days=1)
        return {"action": "START", "scheduledTime": tomorrow_start.isoformat()}


def _calculate_next_daily_action(daily_schedule: WeeklySchedule, now: datetime, tz: ZoneInfo) -> dict[str, str] | None:
    """Calculate next action for daily schedule"""
    current_weekday = now.weekday()

    day_schedules = [
        daily_schedule.monday,  # 0: Monday
        daily_schedule.tuesday,  # 1: Tuesday
        daily_schedule.wednesday,  # 2: Wednesday
        daily_schedule.thursday,  # 3: Thursday
        daily_schedule.friday,  # 4: Friday
        daily_schedule.saturday,  # 5: Saturday
        daily_schedule.sunday,  # 6: Sunday
    ]

    # Check today first
    today_schedule = day_schedules[current_weekday]
    if today_schedule:
        next_action = _get_next_action_for_today(today_schedule, now, tz)
        if next_action:
            return next_action

    # Look ahead for the next 7 days to find the next scheduled action
    for days_ahead in range(1, 8):
        future_date = now.date() + timedelta(days=days_ahead)
        future_weekday = future_date.weekday()
        future_schedule = day_schedules[future_weekday]

        if future_schedule:
            # Found a schedule for this day - next action is START at beginning of that day
            start_hour, start_minute = map(int, future_schedule.startTime.split(":"))
            future_start = datetime.combine(
                future_date, datetime.min.time().replace(hour=start_hour, minute=start_minute)
            ).replace(tzinfo=tz)

            return {"action": "START", "scheduledTime": future_start.isoformat()}
    return None


def _get_next_action_for_today(day_schedule: DaySchedule, now: datetime, tz: ZoneInfo) -> dict[str, str] | None:
    """Get next action for today's schedule only"""
    today = now.date()

    # Parse schedule times
    start_hour, start_minute = map(int, day_schedule.startTime.split(":"))
    stop_hour, stop_minute = map(int, day_schedule.stopTime.split(":"))

    # Create time objects for today
    start_time = datetime.combine(today, datetime.min.time().replace(hour=start_hour, minute=start_minute)).replace(
        tzinfo=tz
    )
    stop_time = datetime.combine(today, datetime.min.time().replace(hour=stop_hour, minute=stop_minute)).replace(
        tzinfo=tz
    )

    # Check what's the next action for today
    if now < start_time:
        return {"action": "START", "scheduledTime": start_time.isoformat()}
    elif now < stop_time:
        return {"action": "STOP", "scheduledTime": stop_time.isoformat()}

    # If we're past stop time today, no more actions for today
    return None


def merge_schedule_data(model_id: str, partial_update: dict[str, Any]) -> dict[str, Any]:
    """Merge partial schedule update with existing schedule data"""
    # Get existing schedule data from model_config.autoScalingConfig.scheduling
    existing_data = {}
    try:
        response = model_table.get_item(Key={"model_id": model_id})
        if "Item" in response:
            model_item = response["Item"]
            model_config = model_item.get("model_config", {})
            auto_scaling_config = model_config.get("autoScalingConfig", {})
            scheduling_data = auto_scaling_config.get("scheduling")

            # Handle case where scheduling exists but is None
            if scheduling_data is not None and isinstance(scheduling_data, dict):
                existing_data = scheduling_data
            else:
                existing_data = {}
    except Exception as e:
        logger.warning(f"Could not get existing schedule for {model_id}: {e}")

    # Merge existing with partial update
    merged_data = {**existing_data, **partial_update}

    # Remove metadata fields that shouldn't come from frontend
    metadata_fields = [
        "scheduledActionArns",
        "scheduleEnabled",
        "lastScheduleUpdate",
        "scheduleConfigured",
        "lastScheduleFailed",
        "nextScheduledAction",
        "lastScheduleFailure",
    ]
    for field in metadata_fields:
        merged_data.pop(field, None)

    return merged_data


def get_existing_scheduled_action_arns(model_id: str) -> list[str]:
    """Get existing scheduled action ARNs for a model"""
    try:
        response = model_table.get_item(Key={"model_id": model_id})

        if "Item" not in response:
            return []

        model_item = response["Item"]
        model_config = model_item.get("model_config", {})
        auto_scaling_config = model_config.get("autoScalingConfig", {})
        scheduling_config = auto_scaling_config.get("scheduling", {})

        return scheduling_config.get("scheduledActionArns", [])  # type: ignore[no-any-return]

    except Exception as e:
        logger.error(f"Failed to get existing scheduled actions for model {model_id}: {e}")
        return []


def update_model_schedule_record(
    model_id: str, scheduling_config: SchedulingConfig | None, scheduled_action_arns: list[str], enabled: bool
) -> None:
    """Update model record in DynamoDB with schedule information"""
    try:
        # Check if model_config.autoScalingConfig exists first
        response = model_table.get_item(Key={"model_id": model_id})
        if "Item" not in response:
            raise ModelNotFoundError(f"Model {model_id} not found")

        model_item = response["Item"]
        model_config_exists = "model_config" in model_item
        auto_scaling_config_exists = model_config_exists and "autoScalingConfig" in model_item.get("model_config", {})

        if scheduling_config:
            # Prepare the scheduling configuration for storage
            schedule_data = scheduling_config.model_dump()
            schedule_data["scheduledActionArns"] = scheduled_action_arns
            schedule_data["scheduleEnabled"] = enabled
            schedule_data["lastScheduleUpdate"] = iso_string()
            schedule_data["scheduleConfigured"] = enabled
            schedule_data["lastScheduleFailed"] = False
            schedule_data["lastScheduleFailure"] = None

            # Update DynamoDB schedule data
            if auto_scaling_config_exists:
                # Update existing model_config.autoScalingConfig.scheduling
                model_table.update_item(
                    Key={"model_id": model_id},
                    UpdateExpression="SET model_config.autoScalingConfig.scheduling = :scheduling",
                    ExpressionAttributeValues={":scheduling": schedule_data},
                )
            else:
                # Create model_config.autoScalingConfig with scheduling
                model_table.update_item(
                    Key={"model_id": model_id},
                    UpdateExpression="SET model_config.autoScalingConfig = :autoScalingConfig",
                    ExpressionAttributeValues={":autoScalingConfig": {"scheduling": schedule_data}},
                )

            # Calculate and update next scheduled action after initial DDB update is saved
            next_action = calculate_next_scheduled_action(scheduling_config, scheduling_config.timezone)
            model_table.update_item(
                Key={"model_id": model_id},
                UpdateExpression="SET model_config.autoScalingConfig.scheduling.nextScheduledAction = :next_action",
                ExpressionAttributeValues={":next_action": next_action},
            )
        else:
            # Set scheduling configuration to null for always run behavior
            if auto_scaling_config_exists:
                model_table.update_item(
                    Key={"model_id": model_id},
                    UpdateExpression="SET model_config.autoScalingConfig.scheduling = :null_scheduling",
                    ExpressionAttributeValues={":null_scheduling": None},
                )
            else:
                # Create model_config.autoScalingConfig with null scheduling
                model_table.update_item(
                    Key={"model_id": model_id},
                    UpdateExpression="SET model_config.autoScalingConfig = :autoScalingConfig",
                    ExpressionAttributeValues={":autoScalingConfig": {"scheduling": None}},
                )

        logger.info(f"Updated schedule record for model {model_id}")

    except Exception as e:
        logger.error(f"Failed to update schedule record for model {model_id}: {e}")
        raise
