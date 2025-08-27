#!/usr/bin/env python3
"""Test script to understand how AskSage handles tools with raw queries."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from asksage_proxy.client import AskSageClient
from asksage_proxy.config import AskSageConfig


async def test_tools_raw():
    """Test raw AskSage API with tools to understand the format."""
    
    # Create a simple config
    api_key = os.getenv("ASK_SAGE_API", "dummy-key")
    if api_key == "dummy-key":
        print("⚠️  Using dummy API key - set ASK_SAGE_API environment variable for real testing")
        
    config = AskSageConfig(
        api_key=api_key,
        asksage_server_base_url="https://api.asksage.anl.gov/server",
        asksage_user_base_url="https://api.asksage.anl.gov/user",
        timeout_seconds=30,
    )
    
    print(f"Testing tools with API key: {config.api_key[:10]}...")
    
    # Define a simple tool (function)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "The temperature unit"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]
    
    try:
        async with AskSageClient(config) as client:
            print("✓ Client initialized successfully")
            
            # Test query with tools
            print("Testing query with tools...")
            payload = {
                "message": "What's the weather like in San Francisco?",
                "model": "gpt-4o",
                "temperature": 0.0,
                "persona": "default",
                "dataset": "all",
                "live": 0,
                "limit_references": 0,
                "tools": json.dumps(tools),  # Convert to JSON string as ANL client does
                "tool_choice": "auto"
            }
            
            print(f"Payload with tools: {json.dumps(payload, indent=2)}")
            
            response = await client.query(payload)
            print(f"✓ Response: {json.dumps(response, indent=2)}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_tools_raw())
    if success:
        print("\n🎉 Tools test completed!")
    else:
        print("\n❌ Tools test failed")