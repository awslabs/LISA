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

"""Pre-generate Prisma client and run DB migrations before LiteLLM workers spawn.

This script runs ONCE in the entrypoint before Gunicorn forks workers, solving two problems:

1. Prisma client write contention: Without pre-generation, multiple Gunicorn workers
   simultaneously try to generate the Prisma Python client to the same filesystem path,
   causing workers 2-N to crash with exit code 1 (the original crash-loop bug).

2. Safe DB migrations: Uses LiteLLM's ProxyExtrasDBManager which handles error recovery,
   baseline creation, and idempotent error resolution — much more robust than raw
   prisma CLI commands.

Concurrency safety across ECS tasks:
- prisma migrate deploy uses PostgreSQL advisory locks internally, so concurrent
  tasks won't conflict on core migrations.
- The post-migration sanity check generates idempotent DDL statements
  (CREATE IF NOT EXISTS, etc.), so concurrent execution across tasks is safe.
"""

import os
import subprocess  # nosec
import sys
from urllib.parse import quote_plus

import boto3
import litellm.proxy
import yaml
from litellm_proxy_extras.utils import ProxyExtrasDBManager


def _get_prisma_schema_dir() -> str:
    """Get the directory containing LiteLLM's schema.prisma."""
    return str(os.path.dirname(litellm.proxy.__file__))


def _generate_prisma_client(schema_dir: str) -> None:
    """Generate the Prisma Python client from LiteLLM's schema.

    This writes the generated client to site-packages/prisma/ once, so that
    Gunicorn workers find it already present and skip generation.
    """
    schema_path = os.path.join(schema_dir, "schema.prisma")
    print(f"Generating Prisma client from {schema_path}")
    result = subprocess.run(  # nosec
        ["prisma", "generate", f"--schema={schema_path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"prisma generate failed (exit {result.returncode}): {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Prisma client generated successfully")


def _build_database_url() -> str | None:
    """Build DATABASE_URL from config or IAM auth environment variables."""
    with open("litellm_config.yaml") as f:
        cfg = yaml.safe_load(f)
    gs = cfg.get("general_settings", {})
    db_url: str | None = gs.get("database_url")
    if db_url:
        return db_url

    if os.environ.get("IAM_TOKEN_DB_AUTH", "").lower() == "true":
        region = os.environ["AWS_REGION"]
        client = boto3.client("rds", region_name=region)
        token: str = client.generate_db_auth_token(
            DBHostname=os.environ["DATABASE_HOST"],
            Port=int(os.environ["DATABASE_PORT"]),
            DBUsername=os.environ["DATABASE_USER"],
            Region=region,
        )
        db_name = os.environ.get("DATABASE_NAME", "postgres")
        return (
            f"postgresql://{os.environ['DATABASE_USER']}:{quote_plus(token)}"
            f"@{os.environ['DATABASE_HOST']}:{os.environ['DATABASE_PORT']}/{db_name}"
        )

    return None


def _run_migrations() -> None:
    """Run database migrations using LiteLLM's ProxyExtrasDBManager."""
    db_url = _build_database_url()
    if not db_url:
        print("No DATABASE_URL available, skipping pre-migration")
        return

    os.environ["DATABASE_URL"] = db_url

    if ProxyExtrasDBManager.setup_database(use_migrate=True):
        print("Migrations applied successfully")
    else:
        print("Migration setup returned False, LiteLLM will handle at startup")


def main() -> None:
    """Generate Prisma client and run DB migrations."""
    schema_dir = _get_prisma_schema_dir()
    print(f"Prisma schema dir: {schema_dir}")

    _generate_prisma_client(schema_dir)
    _run_migrations()


if __name__ == "__main__":
    main()
