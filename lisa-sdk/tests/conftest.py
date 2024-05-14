"""
Sets the input parameters for lisa-sdk tests.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""

from pytest import Parser


def pytest_addoption(parser: Parser) -> None:
    """Set the options for the cli parser."""
    parser.addoption("--url", action="store")
    parser.addoption("--verify", action="store")
