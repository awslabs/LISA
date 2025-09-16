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

"""
Model API Key Cleanup Lambda

This Lambda function removes the api_key field from existing models
that were created with the old LiteLLM version that required api_key = "ignored".
This fixes "Invalid API Key format" errors for models that don't need API keys.

The cleanup runs automatically during CDK deployment via a CustomResource.
"""

import json
import os
import sys
import boto3
import psycopg2
from typing import Dict, Any

# Add the lambda directory to the Python path
sys.path.append('/opt/python')
sys.path.append('/var/task')

from utilities.common_functions import retry_config


def get_database_connection():
    """Get database connection using connection info from SSM."""
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
    
    # Get database connection info from SSM
    db_param_response = ssm_client.get_parameter(Name="/dev/LISA/lisa/LiteLLMDbConnectionInfo")
    db_params = json.loads(db_param_response["Parameter"]["Value"])
    
    # Get database credentials from Secrets Manager
    secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
    secret_response = secrets_client.get_secret_value(SecretId=db_params["passwordSecretId"])
    secret = json.loads(secret_response["SecretString"])
    
    # Create connection
    conn = psycopg2.connect(
        host=db_params["dbHost"],
        port=db_params["dbPort"],
        database=db_params["dbName"],
        user=db_params["username"],
        password=secret["password"]
    )
    return conn


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for model API key cleanup.
    
    Args:
        event: CloudFormation CustomResource event
        context: Lambda context
        
    Returns:
        CloudFormation CustomResource response
    """
    print("🔧 Starting model API key cleanup...")
    
    try:
        # Get database connection
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # First, let's see what tables exist in the database
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = cursor.fetchall()
        print(f"🔍 Available tables in database: {[table[0] for table in tables]}")
        
        # Try to find the correct LiteLLM model table name
        litellm_table = None
        for table in tables:
            table_name = table[0]
            if 'proxymodel' in table_name.lower() or table_name == 'LiteLLM_ProxyModelTable':
                litellm_table = table_name
                print(f"🎯 Found LiteLLM model table: {table_name}")
                break
        
        if not litellm_table:
            print("⚠️ No LiteLLM model table found in database. Database might not be initialized yet.")
            print("🎉 Cleanup completed! 0 Bedrock models updated (no tables found)")
            # Return success response for CloudFormation CustomResource
            return {
                'Status': 'SUCCESS',
                'PhysicalResourceId': 'bedrock-auth-cleanup',
                'Data': {
                    'ModelsUpdated': '0'
                }
            }
        
        # Query all models from the LiteLLM database using the found table (use quotes for case-sensitive names)
        cursor.execute(f'SELECT * FROM "{litellm_table}" LIMIT 1')
        columns = [desc[0] for desc in cursor.description]
        print(f"🔍 Table {litellm_table} columns: {columns}")
        
        # Try to find the correct column names
        model_id_col = next((col for col in columns if 'id' in col.lower()), None)
        model_name_col = next((col for col in columns if 'name' in col.lower()), None)
        litellm_params_col = next((col for col in columns if 'param' in col.lower()), None)
        
        if not all([model_id_col, model_name_col, litellm_params_col]):
            print(f"⚠️ Could not find required columns in table {litellm_table}")
            print(f"    Available columns: {columns}")
            print("🎉 Cleanup completed! 0 Bedrock models updated (table structure unknown)")
            # Return success response for CloudFormation CustomResource
            return {
                'Status': 'SUCCESS',
                'PhysicalResourceId': 'bedrock-auth-cleanup',
                'Data': {
                    'ModelsUpdated': '0'
                }
            }
        
        # Query all models from the LiteLLM database (use quotes for case-sensitive names)
        cursor.execute(f'SELECT "{model_id_col}", "{model_name_col}", "{litellm_params_col}" FROM "{litellm_table}"')
        models = cursor.fetchall()
        
        print(f"🔍 Found {len(models)} total models in LiteLLM database")
        
        models_updated = 0
        
        for model_id, model_name, litellm_params_data in models:
            try:
                # Handle both dict and JSON string formats
                if isinstance(litellm_params_data, dict):
                    litellm_params = litellm_params_data
                elif isinstance(litellm_params_data, str):
                    litellm_params = json.loads(litellm_params_data) if litellm_params_data else {}
                else:
                    litellm_params = {}
            except json.JSONDecodeError:
                print(f"⚠️ Could not parse litellm_params for model {model_name}: {litellm_params_data}")
                continue
            
            model_type = litellm_params.get('model', '')
            has_api_key = 'api_key' in litellm_params
            
            # Debug logging for test-3 model
            if 'test-3' in model_name.lower():
                print(f"🔍 DEBUG - test-3 model details:")
                print(f"    Model name: {model_name}")
                print(f"    Model type: {model_type}")
                print(f"    Has api_key: {has_api_key}")
                print(f"    Full litellm_params: {litellm_params}")
            
            # Process any model that has api_key - remove the problematic field
            if has_api_key:
                print(f"🔧 Removing api_key from model: {model_name} ({model_type})")
                print(f"    Current params: {litellm_params}")
                
                try:
                    # Remove api_key from litellm_params
                    clean_params = litellm_params.copy()
                    if 'api_key' in clean_params:
                        del clean_params['api_key']
                        print(f"    Removed api_key from params")
                    
                    # Update the model in the database (use quotes for case-sensitive names)
                    clean_params_json = json.dumps(clean_params)
                    cursor.execute(
                        f'UPDATE "{litellm_table}" SET "{litellm_params_col}" = %s WHERE "{model_id_col}" = %s',
                        (clean_params_json, model_id)
                    )
                    
                    print(f"✅ Removed api_key from {model_name}")
                    models_updated += 1
                    
                except Exception as e:
                    print(f"⚠️ Could not fix {model_name}: {e}")
                    # Continue with other models
                    continue
            else:
                print(f"✅ Model already clean: {model_name} ({model_type})")
        
        # Commit the changes
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"🎉 Cleanup completed! {models_updated} models updated")
        
        # Return success response for CloudFormation CustomResource
        return {
            'Status': 'SUCCESS',
            'PhysicalResourceId': 'bedrock-auth-cleanup',
            'Data': {
                'ModelsUpdated': str(models_updated)
            }
        }
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        # Return failure response for CloudFormation CustomResource
        return {
            'Status': 'FAILED',
            'PhysicalResourceId': 'bedrock-auth-cleanup',
            'Reason': str(e)
        }
