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

"""Set environment variables for cert locations in Lambda function and load auth plugins."""
import os

region_name = os.environ["AWS_REGION"]
if "iso" in region_name:
    cacerts_directory = "/etc/pki/ca-trust/extracted/pem"
    merged_cert_filename = os.path.join(cacerts_directory, "tls-ca-bundle.pem")
    if not os.environ.get("AWS_CA_BUNDLE"):
        os.environ["AWS_CA_BUNDLE"] = merged_cert_filename
    if not os.environ.get("REQUESTS_CA_BUNDLE"):
        os.environ["REQUESTS_CA_BUNDLE"] = merged_cert_filename
    if not os.environ.get("SSL_CERT_DIR"):
        os.environ["SSL_CERT_DIR"] = cacerts_directory
    if not os.environ.get("SSL_CERT_FILE"):
        os.environ["SSL_CERT_FILE"] = merged_cert_filename

# ============================================================================
# Auth Plugin Loading
# ============================================================================
# Attempt to load auth plugins from Lambda layers. Plugins self-register
# when imported, so we just need to import them if they're available.
# This enables extensibility without modifying core LISA code.

def _load_auth_plugins():
    """Load authorization plugins if available.
    
    This function attempts to import known auth plugin packages that may be
    provided via Lambda layers. Each plugin self-registers its authorization
    provider when imported.
    
    To create a custom auth plugin:
    1. Create a Python package that imports and registers a provider
    2. Package it as a Lambda layer
    3. Add the package name to the auth_plugins list below
    4. Attach the layer to LISA Lambda functions
    """
    # List of known auth plugin packages to try loading
    # Add custom plugin package names here
    auth_plugins: list[str] = [
        # Example: "my_custom_auth_plugin",
    ]
    
    for plugin in auth_plugins:
        try:
            __import__(plugin)
        except ImportError:
            # Plugin not available - this is expected
            pass

# Load auth plugins at module import time
_load_auth_plugins()
