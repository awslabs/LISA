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

"""Constants related to parsing RAG documents."""
PDF_FILE = "pdf"
TEXT_FILE = "txt"
DOCX_FILE = "docx"
RICH_TEXT_FILE = "rtf"


"""Constants for pagination and time limits"""
DEFAULT_TIME_LIMIT_HOURS = 720  # 30 days
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1
