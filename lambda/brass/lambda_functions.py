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

"""BRASS Authorization Lambda functions."""
import json
import logging
from typing import Any, Dict

from utilities.brass_client import BrassClient
from utilities.common_functions import api_wrapper

logger = logging.getLogger(__name__)


def create_cors_headers() -> Dict[str, str]:
    """Create CORS headers for API Gateway responses."""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'OPTIONS,POST'
    }


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a properly formatted API Gateway response.
    
    Parameters
    ----------
    status_code : int
        HTTP status code for the response
    body : Dict[str, Any]
        Response body that will be JSON serialized
        
    Returns
    -------
    Dict[str, Any]
        Properly formatted API Gateway response
    """
    return {
        'statusCode': status_code,
        'headers': create_cors_headers(),
        'body': json.dumps(body, default=str)  # Handle datetime and other non-JSON types
    }


def validate_bindle_guid(bindle_guid: str) -> bool:
    """Validate that a string is a properly formatted Amazon bindle resource GUID.
    
    Parameters
    ----------
    bindle_guid : str
        The bindle GUID to validate
        
    Returns
    -------
    bool
        True if the GUID format is valid, False otherwise
    """
    if not bindle_guid or not isinstance(bindle_guid, str):
        return False
        
    # Amazon bindle resource GUIDs follow the pattern: amzn1.bindle.resource.{guid}
    return bindle_guid.startswith('amzn1.bindle.resource.') and len(bindle_guid) > 22


def validate_username(username: str) -> bool:
    """Validate that a username is properly formatted.
    
    Parameters
    ----------
    username : str
        The username to validate
        
    Returns
    -------
    bool
        True if the username format is valid, False otherwise
    """
    if not username or not isinstance(username, str):
        return False
        
    # Amazon usernames are typically alphanumeric with some allowed special characters
    username = username.strip()
    return len(username) > 0 and len(username) <= 64 and username.replace('-', '').replace('_', '').replace('.', '').isalnum()


@api_wrapper
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for BRASS authorization requests.
    
    This function handles POST requests to check BRASS authorization for bindle locks.
    Expected request format:
    {
        "actor": {
            "actorType": "principal",
            "actorId": "username"
        },
        "operation": "Unlock",
        "resource": {
            "namespace": "Bindle",
            "resourceType": "Lock",
            "resourceName": "amzn1.bindle.resource.xxxxx"
        }
    }
    """
    logger.info(f"BRASS Authorization request: {json.dumps(event, default=str)}")
    
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return create_response(200, {'message': 'CORS preflight successful'})
    
    # Parse the request body
    if 'body' not in event or not event['body']:
        return create_response(400, {'error': 'Missing request body'})
    
    try:
        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body: {e}")
        return create_response(400, {'error': 'Invalid JSON in request body'})
    
    # Validate required fields
    required_fields = ['actor', 'operation', 'resource']
    for field in required_fields:
        if field not in body:
            return create_response(400, {'error': f'Missing required field: {field}'})
    
    # Validate actor structure
    if 'actorType' not in body['actor'] or 'actorId' not in body['actor']:
        return create_response(400, {
            'error': 'Actor must have actorType and actorId fields'
        })
    
    # Validate username format
    if not validate_username(body['actor']['actorId']):
        return create_response(400, {
            'error': 'Actor actorId must be a valid username format'
        })
    
    # Validate resource structure
    required_resource_fields = ['namespace', 'resourceType', 'resourceName']
    for field in required_resource_fields:
        if field not in body['resource']:
            return create_response(400, {
                'error': f'Resource must have {field} field'
            })
    
    # Validate bindle GUID format for bindle lock resources
    if (body['resource']['namespace'] == 'Bindle' and 
        body['resource']['resourceType'] == 'Lock' and
        not validate_bindle_guid(body['resource']['resourceName'])):
        return create_response(400, {
            'error': 'Resource resourceName must be a valid Amazon bindle resource GUID for bindle locks'
        })
    
    # Create BRASS client and make the authorization request
    brass_client = BrassClient()
    
    logger.info(f"Processing BRASS authorization for user: {body['actor']['actorId']}")
    
    # Use the BrassClient to make the authorization request
    is_authorized = brass_client.is_authorized(
        actor_id=body['actor']['actorId'],
        operation=body['operation'],
        namespace=body['resource']['namespace'],
        resource_type=body['resource']['resourceType'],
        resource_name=body['resource']['resourceName'],
        actor_type=body['actor']['actorType']
    )
    
    logger.info(f"BRASS authorization result: {is_authorized}")
    
    # Create successful response
    response_body = {
        'authorized': is_authorized,
        'user': body['actor']['actorId'],
        'bindleLock': body['resource']['resourceName'],
        'request': body,
        'brassResponse': {
            'authorized': is_authorized,
            'user': body['actor']['actorId'],
            'operation': body['operation'],
            'resource': body['resource']
        }
    }
    
    return create_response(200, response_body)
