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
Minimal migration to remove api_key from existing Bedrock models in LiteLLM database.
This allows Bedrock models to use auto-detected AWS credentials from Lambda environment.
"""

import json
import os
import boto3
from models.clients.litellm_client import LiteLLMClient
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint


def lambda_handler(event, context):
    """Remove api_key field from existing Bedrock models to enable AWS credential auto-detection."""
    
    request_type = event.get('RequestType', 'Create')
    
    # Only run on Create/Update, skip Delete
    if request_type == 'Delete':
        return {
            'Status': 'SUCCESS',
            'PhysicalResourceId': 'bedrock-auth-cleanup'
        }
    
    try:
        print("🔧 Starting minimal Bedrock authentication cleanup...")
        
        # Initialize clients
        secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
        iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"])
        
        litellm_client = LiteLLMClient(
            base_uri=get_rest_api_container_endpoint(),
            verify=get_cert_path(iam_client),
            headers={
                "Authorization": secrets_manager.get_secret_value(
                    SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT"
                )["SecretString"],
                "Content-Type": "application/json",
            },
        )
        
        # Get all models from LiteLLM
        all_models = litellm_client.list_models()
        
        if not all_models:
            print("No models found in LiteLLM database")
            return {'Status': 'SUCCESS', 'PhysicalResourceId': 'bedrock-auth-cleanup'}
        
        bedrock_models_updated = 0
        
        for model_entry in all_models:
            model_info = model_entry.get('model_info', {})
            litellm_params = model_info.get('litellm_params', {})
            model_name = litellm_params.get('model', '')
            
            # Check if it's a Bedrock model with api_key
            if model_name.startswith('bedrock/') and 'api_key' in litellm_params:
                model_id = model_info.get('id')
                display_name = model_entry.get('model_name', model_id)
                
                print(f"🔧 Cleaning up Bedrock model: {display_name} ({model_name})")
                
                try:
                    # Create clean params without api_key for Bedrock
                    clean_params = {k: v for k, v in litellm_params.items() if k != 'api_key'}
                    
                    # Delete old model and recreate with clean params
                    litellm_client.delete_model(identifier=model_id)
                    
                    # Recreate without api_key (allows AWS credential auto-detection)
                    litellm_client.add_model(
                        model_name=display_name,
                        litellm_params=clean_params
                    )
                    
                    bedrock_models_updated += 1
                    print(f"✅ Updated {display_name}")
                    
                except Exception as e:
                    print(f"⚠️ Could not update {display_name}: {e}")
                    # Continue with other models
                    continue
        
        print(f"🎉 Cleanup completed! {bedrock_models_updated} Bedrock models updated")
        
        return {
            'Status': 'SUCCESS',
            'PhysicalResourceId': 'bedrock-auth-cleanup',
            'Data': {
                'ModelsUpdated': str(bedrock_models_updated)
            }
        }
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return {
            'Status': 'FAILED',
            'PhysicalResourceId': 'bedrock-auth-cleanup',
            'Reason': str(e)
        }
