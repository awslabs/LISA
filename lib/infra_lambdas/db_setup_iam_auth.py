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
import os
import psycopg2
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any

def get_db_credentials(secret_arn: str) -> Dict[str, str]:
    """Retrieve database credentials from Secrets Manager"""
    client = boto3.client('secretsmanager')

    try:
        response = client.get_secret_value(SecretId=secret_arn)
    except ClientError as e:
        raise Exception(f"Error retrieving secrets: {e}")
    
    secret = response['SecretString']
    secret_dict = eval(secret)  # Converting string to dictionary
    return secret_dict

def create_db_user(db_host: str, db_port: str, db_name: str, db_user: str, 
                   secret_arn: str, iam_role: str) -> None:
    """Create a PostgreSQL user for IAM authentication"""
    # Get credentials from Secrets Manager
    credentials = get_db_credentials(secret_arn)
    
    # Connect to the database as the admin user
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=credentials['password'],
        host=db_host,
        port=db_port
    )

    cursor = conn.cursor()

    # Create the database user for IAM authentication (matching IAM role name)
    iam_role_name = os.environ['IAM_ROLE']  # Use the DB_USER as the IAM role name
    create_user_sql = f'CREATE USER "{iam_role_name}"'
    grant_user_sql = f'GRANT rds_iam to "{iam_role_name}"'
    try:
        cursor.execute(create_user_sql)
        cursor.execute(grant_user_sql)
        conn.commit()
    except psycopg2.Error as e:
        raise Exception(f"Error creating user: {e}")
    finally:
        cursor.close()
        conn.close()

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler"""
    # Extract parameters from the environment and event
    secret_arn = os.environ['SECRET_ARN']
    db_host = os.environ['DB_HOST']
    db_port = os.environ['DB_PORT']
    db_name = os.environ['DB_NAME']
    db_user = os.environ['DB_USER']
    iam_role = os.environ['IAM_ROLE']
    
    # Call function to create DB user
    create_db_user(db_host, db_port, db_name, db_user, secret_arn, iam_role)

    return {
        'statusCode': 200,
        'body': 'Database user created successfully'
    }
