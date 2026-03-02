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


class IamAuthSetupRequest:
    """Request payload for IAM database user setup."""

    def __init__(
        self,
        secret_arn: str,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        iam_name: str,
    ):
        self.secret_arn = secret_arn
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.iam_name = iam_name

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> "IamAuthSetupRequest":
        """Parse and validate request from Lambda event payload."""
        required_fields = {
            "secretArn": "secret_arn",  # pragma: allowlist secret
            "dbHost": "db_host",
            "dbPort": "db_port",
            "dbName": "db_name",
            "dbUser": "db_user",
            "iamName": "iam_name",
        }

        missing = [field for field in required_fields if field not in event]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        return cls(
            secret_arn=str(event["secretArn"]),
            db_host=str(event["dbHost"]),
            db_port=int(event["dbPort"]),
            db_name=str(event["dbName"]),
            db_user=str(event["dbUser"]),
            iam_name=str(event["iamName"]),
        )


def get_db_credentials(secret_arn: str) -> Any | None:
    """Retrieve database credentials from Secrets Manager.

    Returns None if the secret doesn't exist (already deleted after bootstrap).
    """
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])

    try:
        response = client.get_secret_value(SecretId=secret_arn)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            logger.info(f"Bootstrap secret not found (already deleted): {secret_arn}")
            return None
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


def create_db_user(db_host: str, db_port: str, db_name: str, db_user: str, secret_arn: str, iam_name: str) -> bool:
    """Create a PostgreSQL user for IAM authentication.

    Returns True if user was created/updated, False if skipped (secret not found).
    """
    logger.info(f"Starting IAM user creation for: {iam_name}")
    logger.info(f"Database connection details - host: {db_host}, port: {db_port}, dbname: {db_name}, user: {db_user}")

    credentials = get_db_credentials(secret_arn)

    if credentials is None:
        logger.info("Bootstrap secret not found - IAM user was likely already created in a previous run")
        logger.info("Skipping user creation to avoid errors. If permissions need updating, manually run SQL grants.")
        return False

    logger.info("Successfully retrieved bootstrap credentials from Secrets Manager")
    logger.info(f"Connecting to database at {db_host}:{db_port}/{db_name} as {db_user}")

    try:
        conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=credentials["password"], host=db_host, port=db_port
        )
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to database: {e}")
        raise Exception(f"Failed to connect to database: {e}")

    cursor = conn.cursor()

    # Create vector extension (requires superuser privileges from bootstrap user)
    try:
        logger.info("Creating vector extension if not exists")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        logger.info("Vector extension created or already exists")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error creating vector extension: {e}")
        raise Exception(f"Error creating vector extension: {e}")

    try:
        logger.info(f"Creating database user: {iam_name}")
        cursor.execute(f'CREATE USER "{iam_name}"')
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()  # Must rollback failed transaction before executing more commands
        if e.pgcode not in ["23505", "42710"]:
            logger.error(f"Error creating user: {e}")
            raise Exception(f"Error creating user: {e}")
        logger.info(f"User {iam_name} already exists (pgcode: {e.pgcode})")

    sql_commands = [
        f'GRANT rds_iam to "{iam_name}"',
        # Schema-level permissions
        f'GRANT USAGE, CREATE ON SCHEMA public TO "{iam_name}"',
        f'GRANT ALL ON SCHEMA public TO "{iam_name}"',
        # Existing object permissions
        f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON ALL PROCEDURES IN SCHEMA public TO "{iam_name}"',
        # Default privileges for future objects
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO "{iam_name}"',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO "{iam_name}"',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON FUNCTIONS TO "{iam_name}"',
        # Database-level permissions
        f'GRANT CONNECT ON DATABASE "{db_name}" TO "{iam_name}"',
        f'GRANT CREATE ON DATABASE "{db_name}" TO "{iam_name}"',
        f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" TO "{iam_name}"',
        # RDS-specific admin role (provides elevated privileges without SUPERUSER)
        f'GRANT rds_superuser TO "{iam_name}"',
    ]
    try:
        for command in sql_commands:
            logger.info(f"Executing: {command}")
            cursor.execute(command)
        conn.commit()
        logger.info("Successfully granted all privileges to IAM user")
    except psycopg2.Error as e:
        logger.error(f"Error granting privileges to user: {e}")
        raise Exception(f"Error granting privileges to user: {e}")
    finally:
        cursor.close()
        conn.close()

    return True


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for IAM database user setup.

    Creates an IAM-authenticated PostgreSQL user. The bootstrap secret is kept
    for CloudFormation compatibility (not deleted) even though it won't be used
    for authentication after IAM auth is enabled.
    """
    logger.info(f"IAM auth setup Lambda invoked with event: {json.dumps(event)}")

    try:
        request = IamAuthSetupRequest.from_event(event)
        logger.info(
            f"""Parsed request - dbHost: {request.db_host}, dbPort: {request.db_port}, dbName: {request.db_name},
            iamName: {request.iam_name}"""
        )
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Invalid request payload: {e}")
        return {"statusCode": 400, "body": json.dumps({"error": f"Invalid request payload: {e}"})}

    try:
        user_created = create_db_user(
            request.db_host,
            str(request.db_port),
            request.db_name,
            request.db_user,
            request.secret_arn,
            request.iam_name,
        )

        # Note: We no longer delete the bootstrap secret to maintain CloudFormation compatibility
        # The secret remains but is not used for authentication when IAM auth is enabled
        logger.info("IAM user setup complete. Bootstrap secret retained for CloudFormation compatibility.")

        result = {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Database user setup complete",
                    "userCreated": user_created,
                    "secretDeleted": False,  # Secret is retained
                }
            ),
        }
        logger.info(f"IAM auth setup completed successfully: {result}")
        return result

    except Exception as e:
        logger.error(f"IAM auth setup failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
