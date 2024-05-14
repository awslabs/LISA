"""Public imports.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
import os
import sys

from loguru import logger

from .ecs import *  # noqa: F403,F401

# Configure custom logger
logger.remove()
logger_level = os.environ.get("LOG_LEVEL", "INFO")
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{request_id}</cyan> | {message}",
            "level": logger_level.upper(),
        }
    ]
)
