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
from typing import Any

import boto3
import psycopg2
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_db_credentials(secret_arn: str) -> Any:
    """Retrieve database credentials from Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])

    try:
        response = client.get_secret_value(SecretId=secret_arn)
    except ClientError as e:
        raise Exception(f"Error retrieving secrets: {e}")

    secret = response["SecretString"]
    secret_dict = json.loads(secret)
    return secret_dict


def delete_bootstrap_secret(secret_arn: str) -> bool:
    """Delete the bootstrap password secret from Secrets Manager.

    Returns True if secret was deleted, False if deletion was skipped or failed.
    """
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])

    try:
        client.delete_secret(SecretId=secret_arn, ForceDeleteWithoutRecovery=True)
        logger.info(f"Successfully deleted bootstrap secret: {secret_arn}")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            logger.info(f"Bootstrap secret already deleted: {secret_arn}")
            return True
        logger.error(f"Failed to delete bootstrap secret: {e}")
        return False


def create_db_user(db_host: str, db_port: str, db_name: str, db_user: str, secret_arn: str, iam_name: str) -> None:
    """Create a PostgreSQL user for IAM authentication."""
    credentials = get_db_credentials(secret_arn)

    conn = psycopg2.connect(dbname=db_name, user=db_user, password=credentials["password"], host=db_host, port=db_port)
    cursor = conn.cursor()

    try:
        cursor.execute(f'CREATE USER "{iam_name}"')
        conn.commit()
    except psycopg2.Error as e:
        if e.pgcode not in ["23505", "42710"]:
            raise Exception(f"Error creating user: {e}")

    sql_commands = [
        f'GRANT rds_iam to "{iam_name}"',
        f'GRANT USAGE, CREATE ON SCHEMA public TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON ALL PROCEDURES IN SCHEMA public TO "{iam_name}"',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO "{iam_name}"',
        f'GRANT CONNECT ON DATABASE "{db_name}" TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" TO "{iam_name}"',
    ]
    try:
        for command in sql_commands:
            cursor.execute(command)
        conn.commit()
    except psycopg2.Error as e:
        raise Exception(f"Error granting privileges to user: {e}")
    finally:
        cursor.close()
        conn.close()


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for IAM database user setup.

    Creates an IAM-authenticated PostgreSQL user and optionally deletes the
    bootstrap password secret afterward.
    """
    secret_arn = os.environ["SECRET_ARN"]
    db_host = os.environ["DB_HOST"]
    db_port = os.environ["DB_PORT"]
    db_name = os.environ["DB_NAME"]
    db_user = os.environ["DB_USER"]
    iam_name = os.environ["IAM_NAME"]

    create_db_user(db_host, db_port, db_name, db_user, secret_arn, iam_name)
    secret_deleted = delete_bootstrap_secret(secret_arn)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Database user created successfully",
                "secretDeleted": secret_deleted,
            }
        ),
    }
