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

"""BRASS Authorization Client for LISA."""
import logging
import os
from typing import Optional

import boto3
import six
from com.amazon.brass.coral.calls.brassservice import BrassServiceClient
from com.amazon.brass.coral.calls.isauthorizedrequest import IsAuthorizedRequest
from com.amazon.brass.coral.types.actorreference import ActorReference
from com.amazon.brass.coral.types.resourcereference import ResourceReference
from coral.coralrpc import new_orchestrator

logger = logging.getLogger(__name__)


class BrassClient:
    """BRASS Authorization Client for handling bindle lock and general authorization requests."""
    
    def __init__(self, endpoint: Optional[str] = None, region: Optional[str] = None):
        """Initialize the BRASS client.
        
        Parameters
        ----------
        endpoint : Optional[str]
            BRASS endpoint URL. If not provided, will use BRASS_ENDPOINT environment variable
            or default to US East 1 production endpoint.
        region : Optional[str]
            AWS region for the BRASS service. If not provided, will use BRASS_REGION environment variable
            or attempt to extract from endpoint as fallback.
        """
        self.endpoint = endpoint or os.environ.get(
            "BRASS_ENDPOINT", 
            "https://awsauth.us-east-1.prod.brass.a2z.com"
        )
        self.region = region or os.environ.get("BRASS_REGION", "us-east-1")
        self._client: Optional[BrassServiceClient] = None
    
    def _get_client(self) -> BrassServiceClient:
        """Get or create BRASS coral client with proper credentials and endpoint configuration.
        
        Returns
        -------
        BrassServiceClient
            Configured BRASS service client
        """
        if self._client is None:
            # Get AWS credentials
            credentials = boto3.Session().get_credentials()
            
            # Create coral client for BrassService
            self._client = BrassServiceClient(
                new_orchestrator(
                    endpoint=self.endpoint,
                    timeout=10,
                    aws_region=self.region,
                    aws_service="BrassService",
                    signature_algorithm="v4",
                    aws_access_key=six.b(credentials.access_key),
                    aws_secret_key=six.b(credentials.secret_key),
                    aws_security_token=six.b(credentials.token) if credentials.token else None,
                )
            )
        
        return self._client
    
    def is_authorized(self, actor_id: str, operation: str, namespace: str, 
                     resource_type: str, resource_name: str, 
                     actor_type: str = "principal") -> bool:
        """Check if an actor is authorized to perform an operation on a resource.
        
        Parameters
        ----------
        actor_id : str
            The username/principal ID to check authorization for
        operation : str
            The operation to check (e.g., "Access", "Unlock")
        namespace : str
            The resource namespace (e.g., "Bindle")
        resource_type : str
            The resource type (e.g., "Lock")
        resource_name : str
            The specific resource identifier
        actor_type : str, optional
            The type of actor, by default "principal"
            
        Returns
        -------
        bool
            True if authorized, False otherwise
        """
        try:
            logger.info(f"Authorizing user {actor_id} for {operation} on {namespace}:{resource_type}:{resource_name}")
            
            # Create actor and resource references
            actor = ActorReference(actor_type=actor_type, actor_id=actor_id)
            resource = ResourceReference(
                namespace=namespace,
                resource_type=resource_type,
                resource_name=resource_name
            )
            
            # Create authorization request
            request = IsAuthorizedRequest(actor=actor, operation=operation, resource=resource)
            
            # Make the request using coral client
            client = self._get_client()
            response = client.is_authorized(request)
            
            logger.info(f"BRASS authorization result for {actor_id}: {response.authorized}")
            return response.authorized
                
        except Exception as e:
            logger.error(f"Error calling BRASS API: {str(e)}", exc_info=True)
            return False
    
    def check_bindle_lock_access(self, actor_id: str, bindle_resource_name: str, 
                                operation: str = "Unlock") -> bool:
        """Check if user has access to a specific bindle lock.
        
        Parameters
        ----------
        actor_id : str
            The username to check authorization for
        bindle_resource_name : str
            The GUID of the bindle lock resource
        operation : str, optional
            The operation to check, by default "Unlock"
            
        Returns
        -------
        bool
            True if user has access, False otherwise
        """
        return self.is_authorized(
            actor_id=actor_id,
            operation=operation,
            namespace="Bindle",
            resource_type="Lock",
            resource_name=bindle_resource_name
        )
    
    def check_admin_access(self, username: str, admin_bindle_guid: Optional[str] = None) -> bool:
        """Check if user has admin access via admin bindle lock.
        
        Parameters
        ----------
        username : str
            The username to check admin access for
        admin_bindle_guid : Optional[str]
            The admin bindle GUID. If not provided, will use ADMIN_BINDLE_GUID environment variable.
            
        Returns
        -------
        bool
            True if user has admin access, False otherwise
            
        Raises
        ------
        ValueError
            If username is empty or None
        """
        if not username or not username.strip():
            raise ValueError("Username cannot be empty or None")
            
        bindle_guid = admin_bindle_guid or os.environ.get("ADMIN_BINDLE_GUID", "")
        if not bindle_guid:
            logger.warning("No admin bindle GUID provided or configured in ADMIN_BINDLE_GUID")
            return False
        
        return self.check_bindle_lock_access(username.strip(), bindle_guid, "Unlock")
    
    def check_app_access(self, username: str, app_bindle_guid: Optional[str] = None) -> bool:
        """Check if user has general app access via app bindle lock.
        
        Parameters
        ----------
        username : str
            The username to check app access for
        app_bindle_guid : Optional[str]
            The app bindle GUID. If not provided, will use APP_BINDLE_GUID environment variable.
            
        Returns
        -------
        bool
            True if user has app access, False otherwise
            
        Raises
        ------
        ValueError
            If username is empty or None
        """
        if not username or not username.strip():
            raise ValueError("Username cannot be empty or None")
            
        bindle_guid = app_bindle_guid or os.environ.get("APP_BINDLE_GUID", "")
        if not bindle_guid:
            logger.warning("No app bindle GUID provided or configured in APP_BINDLE_GUID, allowing access")
            return True  # Default to allow if not configured
        
        return self.check_bindle_lock_access(username.strip(), bindle_guid, "Unlock")


# Convenience function for backward compatibility
def get_brass_client(endpoint: Optional[str] = None, region: Optional[str] = None) -> BrassClient:
    """Get a configured BRASS client instance.
    
    Parameters
    ----------
    endpoint : Optional[str]
        BRASS endpoint URL. If not provided, uses environment variable or default.
    region : Optional[str]
        AWS region for the BRASS service. If not provided, uses environment variable or
        attempts to extract from endpoint as fallback.
        
    Returns
    -------
    BrassClient
        Configured BRASS client instance
    """
    return BrassClient(endpoint=endpoint, region=region)
