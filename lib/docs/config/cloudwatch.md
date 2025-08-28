# Usage Analytics

LISA offers Administrators insights into user engagement, feature adoption, and system utilization. Through Amazon CloudWatch, LISA automatically tracks user interactions, RAG usage, MCP tool calls, and group-level analytics, presenting this data through an integrated dashboard and API endpoints.

## Overview
LISA usage data enables administrators to understand user behavior patterns, monitor feature adoption, and make data-driven decisions about system optimization. LISA tracks three primary categories:

- **User Engagement**: Total prompts and users
- **Feature Utilization**: RAG usage patterns and MCP tool adoption
- **Organizational Insights**: Group-level analytics and membership distributions

Metrics are collected in real-time and aggregated for both immediate monitoring and long-term trend analysis.

## CloudWatch Dashboard

### Accessing the Dashboard

The LISA Metrics Dashboard is automatically created during deployment. Administrators can be accessed through the AWS Management Console:

1. Navigate to the **CloudWatch** service in your AWS console
2. Select **Dashboards** from the left navigation menu
3. Locate and click on **LISA-Metrics** dashboard. Click on it to open
4. The dashboard displays a 7-day view by default


### Dashboard Widgets

The dashboard contains 12 widgets organized to provide comprehensive visibility into system usage:

#### Total Prompts
Displays the count of all user prompts over a given time period. This time-series graph shows overall system engagement and helps identify usage trends, peak hours, and growth patterns. It updates hourly with sum statistics.


#### Total RAG Usage
Tracks Retrieval Augmented Generation (RAG) feature adoption across all users. This indicates how frequently users leverage vector stores. Updates hourly with sum statistics.


#### Total MCP Tool Calls
Monitors Model Context Protocol (MCP) tool utilization system-wide. This graph reveals which external integrations are most valuable to users and helps identify opportunities for expanding MCP tool offerings. Aggregates tool calls across all available MCP servers.


#### Prompts by User
Breaks down the prompt activity by individual users, enabling identification of power users and usage distribution patterns.


#### RAG Usage by User
Provides user-level RAG adoption usage, showing which users are actively leveraging vector stores.


#### MCP Tool Calls by User
Displays MCP tool usage at the individual user level, helping administrators identify which users are most engaged with external integrations.


#### MCP Tool Calls by Tool
Shows utilization breakdown by specific MCP tools, enabling administrators to understand which integrations provide the most value and which might need promotion or improvement.


#### Total User Count
Displays the count of users who have interacted with the system. This single-value widget updates daily and provides a high-level view of user base size and growth.


#### Groups by Membership Count
Pie chart visualization showing user distribution across organizational groups. Helps administrators understand team sizes, group engagement levels, and organizational adoption patterns. Updates daily.


#### Group Prompt Counts
Tracks prompt activity aggregated by organizational groups, enabling administrators to understand which teams or departments are most engaged with LISA.


#### Group RAG Usage
Monitors RAG feature adoption at the group level.


#### Group MCP Usage
Displays MCP tool utilization by organizational groups.


## Data Storage


Usage data is stored in multiple locations:

### DynamoDB Storage
- **Usage Metrics Table**: Stores aggregate usage metrics including total prompts, RAG usage counts, MCP tool usage, and group memberships
- **Session-Level Tracking**: Detailed per-session metrics to support accurate counting and prevent data duplication
- **Real-Time Updates**: Session data updates immediately as users interact with LISA

### CloudWatch Metrics
- **Namespace**: All metrics are published under LISA/UsageMetrics
- **Dimensions**: Supports filtering by UserId, GroupName, and ToolName

## Customizing Time Ranges

CloudWatch provides flexible time range customization options for analyzing metrics across different periods:

### Quick Time Range Selection
1. **Dashboard Level**: Use the time range selector at the top-right of the dashboard
2. **Available Options**:
- Last hour, 3 hours, 12 hours, last day, 3 days, week
- Custom relative and absolute ranges from the range selector dropdown

### Widget-Level Customization
1. Click the **three dots** menu on any individual widget
2. Select **Edit** to access advanced options
3. **Period Settings**: Adjust data point intervals (1 day to 1 minute)
4. **Statistic Options**: Choose between Sum, Average, Maximum, Minimum, etc. . .
5. **Time Range Override**: Set widget-specific time ranges independent of dashboard settings


## Data Availability and Timing

Understanding when meaningful data becomes available is crucial for effective analysis:

### Update Frequencies
- **Daily Metrics**: User counts and group membership statistics refresh once daily
- **Session Metrics**: Individual session data is updated in real-time, but may not immediately be visible on the CloudWatch widgets unless the period of the widget is changed or sufficient time passes for it to become visible (given default period and time range).

## Dashboard Management

### Customization and Overrides
CloudWatch allows extensive dashboard customization to meet specific organizational needs:

1. **Widget Modification**: Click any widget's menu to edit titles, colors, and display options
2. **Layout Changes**: Drag and drop widgets to reorganize dashboard layout

### Saving Changes
- **Manual Save**: A change to the dashboard can be saved using the **Save** button in the top right to preserve customizations. A change to a widget can be saved using using the **Update widget** button on the bottom of the edit widget modal.
- **Auto-Save**: Auto-save can be configure on the dashboard by clicking the **Autosave** button which appears above the refresh button on the dashboard screen, and toggling Autosave to be on.

### Deployment Considerations
**Important**: Custom dashboard modifications are overwritten during LISA redeployments. To preserve customizations:

1. **Document Changes**: Keep records of custom configurations
2. **Copy Source**: From the CloudWatch dashboard select **Actions** and **View/edit source**. This will show you the source code of the dashboard which can be copied and reused.
3. **Create Copy**: CloudWatch dashboard select **Actions** and **Save dashboard as**. Provide a unique name and a copy of the `LISA-Metrics` dashboard will be made.


## Daily Metrics Management

### Automated Daily Processing
The system includes a dedicated Lambda function that runs daily to update metrics that change infrequently:

- Unique User Counts
- Group Membership Counts

### Manual Invocation
Administrators can manually trigger daily metrics updates when needed:

#### AWS Console Method
1. Navigate to **Lambda** in the AWS Management Console
2. Locate the **DailyMetricsLambda** function (prefixed with your deployment name)
3. Use the **Test** functionality to invoke the function (can be invoked with empty event JSON)
4. Monitor execution through CloudWatch Logs

#### AWS CLI Method
```bash
aws —region {REGION} lambda invoke \
 —function-name <deployment-prefix>-DailyMetricsLambda \
 —payload '{}' \
 response.json
```

### Troubleshooting
If metrics appear inconsistent or incomplete:
1. Check CloudWatch Logs for the metrics processing Lambda functions
2. Verify SQS queue processing for any backlogs
3. Manually invoke the daily metrics Lambda if aggregate numbers seem outdated
