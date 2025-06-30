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

"""Daily scheduled Lambda function to publish unique users and group membership metrics."""
import os
import boto3
import logging
from datetime import datetime
import create_env_variables  # noqa: F401
from utilities.common_functions import retry_config

logger = logging.getLogger(__name__)

def count_unique_users_and_publish_metric():
    """Count unique users in metrics table and publish to CloudWatch."""
    try:
        # Initialize resources
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        cloudwatch = boto3.client('cloudwatch', region_name=os.environ["AWS_REGION"])
        metrics_table = dynamodb.Table(os.environ["USER_METRICS_TABLE_NAME"])
        
        # Scan the table to get all users
        response = metrics_table.scan(Select='COUNT')
        unique_user_count = response['Count']
        
        # Publish metric to CloudWatch
        cloudwatch.put_metric_data(
            Namespace='LISA/UserMetrics',
            MetricData=[
                {
                    'MetricName': 'UniqueUsers',
                    'Value': unique_user_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.now()
                }
            ]
        )
        logger.info(f"Published unique users metric: {unique_user_count}")
        return unique_user_count
    except Exception as e:
        logger.error(f"Error publishing unique users metric: {e}")
        raise

def count_users_by_group_and_publish_metric():
    """Count users in each group and publish metrics to CloudWatch."""
    try:
        # Initialize resources
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        cloudwatch = boto3.client('cloudwatch', region_name=os.environ["AWS_REGION"])
        metrics_table = dynamodb.Table(os.environ["USER_METRICS_TABLE_NAME"])
        
        # Scan the table to get users with groups
        response = metrics_table.scan(
            ProjectionExpression="userGroups"
        )

        # Count users in each group
        group_counts = {}
        for item in response.get('Items', []):
            if 'userGroups' in item:
                for group in item['userGroups']:
                    group_counts[group] = group_counts.get(group, 0) + 1

        # Publish metrics to CloudWatch
        timestamp = datetime.now()
        metric_data = []
        
        for group, count in group_counts.items():
            metric_data.append({
                'MetricName': 'UsersPerGroup',
                'Dimensions': [
                    {
                        'Name': 'GroupName',
                        'Value': group
                    }
                ],
                'Value': count,
                'Unit': 'Count',
                'Timestamp': timestamp
            })
        
        if metric_data:
            cloudwatch.put_metric_data(
                Namespace='LISA/UserMetrics',
                MetricData=metric_data
            )
        
        logger.info(f"Published user counts by group: {group_counts}")
        return group_counts
        
    except Exception as e:
        logger.error(f"Error publishing user counts by group: {e}")
        raise


def handler(event, context):
    """Lambda handler function for scheduled unique user metrics."""
    return count_unique_users_and_publish_metric(), count_users_by_group_and_publish_metric()
