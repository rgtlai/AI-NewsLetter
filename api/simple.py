"""Simplified FastAPI app for testing deployment without external dependencies"""

def handler(event, context):
    """Simple Lambda handler for testing"""
    
    # Simple response that mimics API Gateway format
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': '{"status":"ok","message":"Simple test API is working","path":"' + event.get('path', '/') + '"}'
    }
