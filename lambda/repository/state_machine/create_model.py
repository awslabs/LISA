"""Lambda function for handling state machine failures."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def handle_failure(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle failures in the state machine execution.
    
    Args:
        event: Event containing error information
        context: Lambda context
        
    Returns:
        Dict with error information
    """
    error = event.get('error', {})
    logger.error(f"State machine execution failed: {error}")
    
    return {
        "statusCode": 500,
        "body": {
            "message": "Pipeline execution failed",
            "error": error
        }
    }
