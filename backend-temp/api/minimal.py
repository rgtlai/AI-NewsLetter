"""Minimal FastAPI app that works without external dependencies"""
import json
import os
from typing import Dict

# Simulate the RSS sources without requiring httpx
DEFAULT_FEEDS: Dict[str, str] = {
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "The Gradient": "https://thegradient.pub/rss/",
    "MIT Technology Review AI": "https://www.technologyreview.com/tag/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/ai/feed/",
    "AI News": "https://artificialintelligence-news.com/feed/",
}

def handler(event, context):
    """Lambda handler that simulates FastAPI responses"""
    
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    # Handle different endpoints
    if path == '/' or path == '/dev/' or path == '/dev':
        body = {"status": "ok", "message": "AI Newsletter API is running"}
    elif path == '/defaults' or path == '/dev/defaults':
        body = DEFAULT_FEEDS
    elif path == '/aggregate' or path == '/dev/aggregate':
        # Mock aggregate response
        body = {
            "status": "success",
            "articles": [
                {
                    "title": "Sample AI Article",
                    "url": "https://example.com/ai-article",
                    "published": "2025-08-09",
                    "source": "AI News",
                    "summary": "This is a sample article about AI developments."
                }
            ],
            "total_articles": 1
        }
    else:
        return {
            'statusCode': 404,
            'headers': headers,
            'body': json.dumps({"detail": "Not Found"})
        }
    
    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(body)
    }
