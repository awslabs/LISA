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

"""Unit tests for scheduling domain objects."""

import pytest
from models.domain_objects import (
    DaySchedule,
    DeleteScheduleResponse,
    GetScheduleResponse,
    GetScheduleStatusResponse,
    NextScheduledAction,
    ScheduleFailure,
    ScheduleType,
    SchedulingConfig,
    UpdateScheduleResponse,
    WeeklySchedule,
)
from pydantic import ValidationError


class TestDaySchedule:
    """Test DaySchedule domain object."""

    def test_valid_day_schedule(self):
        """Test valid day schedule creation."""
        schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        assert schedule.startTime == "09:00"
        assert schedule.stopTime == "17:00"

    def test_invalid_time_format(self):
        """Test invalid time format raises ValidationError."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            DaySchedule(startTime="25:00", stopTime="17:00")

        with pytest.raises(ValidationError, match="String should match pattern"):
            DaySchedule(startTime="09:00", stopTime="25:00")

        with pytest.raises(ValidationError, match="String should match pattern"):
            DaySchedule(startTime="invalid", stopTime="17:00")

    def test_minimum_duration_validation(self):
        """Test minimum 2-hour duration validation."""
        # Valid: 8 hours
        DaySchedule(startTime="09:00", stopTime="17:00")

        # Valid: exactly 2 hours
        DaySchedule(startTime="09:00", stopTime="11:00")

        # Invalid: 1 hour
        with pytest.raises(ValidationError, match="Stop time must be at least 2 hours after start time"):
            DaySchedule(startTime="09:00", stopTime="10:00")

        # Invalid: 30 minutes
        with pytest.raises(ValidationError, match="Stop time must be at least 2 hours after start time"):
            DaySchedule(startTime="09:00", stopTime="09:30")

    def test_cross_midnight_schedule(self):
        """Test cross-midnight schedule validation."""
        # Valid: 22:00 to 02:00 (4 hours)
        schedule = DaySchedule(startTime="22:00", stopTime="02:00")
        assert schedule.startTime == "22:00"
        assert schedule.stopTime == "02:00"

        # Invalid: 23:00 to 00:30 (1.5 hours)
        with pytest.raises(ValidationError, match="Stop time must be at least 2 hours after start time"):
            DaySchedule(startTime="23:00", stopTime="00:30")


class TestWeeklySchedule:
    """Test WeeklySchedule domain object."""

    def test_valid_weekly_schedule(self):
        """Test valid weekly schedule creation."""
        monday_schedule = [DaySchedule(startTime="09:00", stopTime="17:00")]
        tuesday_schedule = [DaySchedule(startTime="10:00", stopTime="18:00")]

        weekly = WeeklySchedule(monday=monday_schedule, tuesday=tuesday_schedule)
        assert len(weekly.monday) == 1
        assert len(weekly.tuesday) == 1
        assert weekly.wednesday is None

    def test_multiple_periods_per_day(self):
        """Test multiple time periods per day."""
        morning_schedule = DaySchedule(startTime="09:00", stopTime="12:00")
        afternoon_schedule = DaySchedule(startTime="13:00", stopTime="17:00")

        weekly = WeeklySchedule(monday=[morning_schedule, afternoon_schedule])
        assert len(weekly.monday) == 2

    def test_overlapping_schedules_validation(self):
        """Test overlapping schedules raise ValidationError."""
        overlap_schedule1 = DaySchedule(startTime="09:00", stopTime="13:00")
        overlap_schedule2 = DaySchedule(startTime="12:00", stopTime="16:00")

        with pytest.raises(ValidationError, match="Monday has overlapping schedules"):
            WeeklySchedule(monday=[overlap_schedule1, overlap_schedule2])


class TestSchedulingConfig:
    """Test SchedulingConfig domain object."""

    def test_recurring_daily_schedule(self):
        """Test RECURRING_DAILY schedule type."""
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        config = SchedulingConfig(
            scheduleType=ScheduleType.RECURRING_DAILY, timezone="UTC", dailySchedule=daily_schedule
        )

        assert config.scheduleType == ScheduleType.RECURRING_DAILY
        assert config.timezone == "UTC"
        assert config.dailySchedule == daily_schedule
        assert config.weeklySchedule is None

    def test_each_day_schedule(self):
        """Test EACH_DAY schedule type."""
        monday_schedule = [DaySchedule(startTime="09:00", stopTime="17:00")]
        weekly_schedule = WeeklySchedule(monday=monday_schedule)

        config = SchedulingConfig(
            scheduleType=ScheduleType.EACH_DAY, timezone="America/New_York", weeklySchedule=weekly_schedule
        )

        assert config.scheduleType == ScheduleType.EACH_DAY
        assert config.weeklySchedule == weekly_schedule
        assert config.dailySchedule is None

    def test_none_schedule_type(self):
        """Test None schedule type."""
        config = SchedulingConfig(scheduleType=None)

        assert config.scheduleType is None
        assert config.dailySchedule is None
        assert config.weeklySchedule is None

    def test_invalid_schedule_consistency(self):
        """Test invalid schedule consistency raises ValidationError."""
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")

        # RECURRING_DAILY with weeklySchedule should fail
        with pytest.raises(ValidationError, match="weeklySchedule not allowed for RECURRING_DAILY type"):
            SchedulingConfig(
                scheduleType=ScheduleType.RECURRING_DAILY,
                dailySchedule=daily_schedule,
                weeklySchedule=WeeklySchedule(monday=[daily_schedule]),
            )

        # EACH_DAY without weeklySchedule should fail
        with pytest.raises(ValidationError, match="weeklySchedule with at least one day required for EACH_DAY type"):
            SchedulingConfig(scheduleType=ScheduleType.EACH_DAY)

    def test_timezone_validation(self):
        """Test timezone validation."""
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")

        # Valid timezone
        config = SchedulingConfig(
            scheduleType=ScheduleType.RECURRING_DAILY, timezone="America/New_York", dailySchedule=daily_schedule
        )
        assert config.timezone == "America/New_York"

        # UTC should always be valid
        config = SchedulingConfig(
            scheduleType=ScheduleType.RECURRING_DAILY, timezone="UTC", dailySchedule=daily_schedule
        )
        assert config.timezone == "UTC"

    def test_invalid_timezone_validation(self):
        """Test invalid timezone raises ValidationError."""
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")

        # Test various invalid timezone formats
        invalid_timezones = [
            "Invalid/Timezone",
            "NotReal/Zone",
            "BadFormat",
            "America/NonExistent",
            "123/456",
            "fake_timezone",
            "UTC/Invalid",
        ]

        for invalid_tz in invalid_timezones:
            with pytest.raises(
                ValidationError, match="Invalid timezone.*timezone must be a valid IANA timezone identifier"
            ):
                SchedulingConfig(
                    scheduleType=ScheduleType.RECURRING_DAILY, timezone=invalid_tz, dailySchedule=daily_schedule
                )


class TestNextScheduledAction:
    """Test NextScheduledAction domain object."""

    def test_valid_next_scheduled_action(self):
        """Test valid NextScheduledAction creation."""
        action = NextScheduledAction(action="START", scheduledTime="2025-01-15T09:00:00Z")

        assert action.action == "START"
        assert action.scheduledTime == "2025-01-15T09:00:00Z"

    def test_invalid_action(self):
        """Test invalid action raises ValidationError."""
        with pytest.raises(ValidationError):
            NextScheduledAction(action="INVALID", scheduledTime="2025-01-15T09:00:00Z")


class TestScheduleFailure:
    """Test ScheduleFailure domain object."""

    def test_schedule_failure(self):
        """Test ScheduleFailure creation."""
        failure = ScheduleFailure(timestamp="2025-01-15T10:00:00Z", error="Auto Scaling Group not found", retryCount=3)

        assert failure.timestamp == "2025-01-15T10:00:00Z"
        assert failure.error == "Auto Scaling Group not found"
        assert failure.retryCount == 3


class TestScheduleResponseObjects:
    """Test Schedule response objects."""

    def test_update_schedule_response(self):
        """Test UpdateScheduleResponse."""
        response = UpdateScheduleResponse(
            message="Schedule updated successfully", modelId="test-model", scheduleEnabled=True
        )

        assert response.message == "Schedule updated successfully"
        assert response.modelId == "test-model"
        assert response.scheduleEnabled is True

    def test_get_schedule_response(self):
        """Test GetScheduleResponse."""
        scheduling_data = {"scheduleType": "RECURRING_DAILY", "timezone": "UTC"}
        next_action = {"action": "START", "scheduledTime": "2025-01-15T09:00:00Z"}

        response = GetScheduleResponse(
            modelId="test-model", scheduling=scheduling_data, nextScheduledAction=next_action
        )

        assert response.modelId == "test-model"
        assert response.scheduling == scheduling_data
        assert response.nextScheduledAction == next_action

    def test_delete_schedule_response(self):
        """Test DeleteScheduleResponse."""
        response = DeleteScheduleResponse(
            message="Schedule deleted successfully", modelId="test-model", scheduleEnabled=False
        )

        assert response.message == "Schedule deleted successfully"
        assert response.modelId == "test-model"
        assert response.scheduleEnabled is False

    def test_get_schedule_status_response(self):
        """Test GetScheduleStatusResponse."""
        response = GetScheduleStatusResponse(
            modelId="test-model",
            scheduleEnabled=True,
            scheduleConfigured=True,
            lastScheduleFailed=False,
            scheduleStatus="ACTIVE",
            scheduleType="RECURRING_DAILY",
            timezone="UTC",
            nextScheduledAction={"action": "START", "scheduledTime": "2025-01-15T09:00:00Z"},
            lastScheduleUpdate="2025-01-14T12:00:00Z",
            lastScheduleFailure=None,
        )

        assert response.modelId == "test-model"
        assert response.scheduleEnabled is True
        assert response.scheduleConfigured is True
        assert response.lastScheduleFailed is False
        assert response.scheduleStatus == "ACTIVE"
        assert response.scheduleType == "RECURRING_DAILY"
        assert response.timezone == "UTC"
