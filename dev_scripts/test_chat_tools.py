#!/usr/bin/env python3
"""Test script to test chat completions endpoint with tools through the proxy."""

import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp

async def test_chat_tools():
    """Test chat completions endpoint with tools."""
    
    # Test data with tools
    test_data = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "What's the weather like in San Francisco? Please use the weather function."
            }
        ],
        "tools": [
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
        ],
        "tool_choice": "auto",
        "temperature": 0.0,
        "stream": False
    }
    
    print("🧪 Testing chat completions with tools...")
    print(f"Request data: {json.dumps(test_data, indent=2)}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:53169/v1/chat/completions",
                json=test_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('ASK_SAGE_API', 'dummy-key')}"
                }
            ) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    response_data = await response.json()
                    print(f"✓ Success! Response: {json.dumps(response_data, indent=2)}")
                    
                    # Check if response has tool calls
                    choices = response_data.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        tool_calls = message.get("tool_calls")
                        if tool_calls:
                            print(f"🔧 Tool calls detected: {tool_calls}")
                        else:
                            print("📝 Regular text response (no tool calls)")
                    
                    return True
                else:
                    error_text = await response.text()
                    print(f"✗ Error {response.status}: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


async def test_chat_tools_streaming():
    """Test chat completions endpoint with tools and streaming."""
    
    # Test data with tools and streaming
    test_data = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "What's the weather like in New York? Use the weather function if needed."
            }
        ],
        "tools": [
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
                                "description": "The city and state, e.g. New York, NY"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ],
        "tool_choice": "auto",
        "temperature": 0.0,
        "stream": True
    }
    
    print("\n🌊 Testing streaming chat completions with tools...")
    print(f"Request data: {json.dumps(test_data, indent=2)}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:53169/v1/chat/completions",
                json=test_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('ASK_SAGE_API', 'dummy-key')}"
                }
            ) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    print("✓ Streaming response:")
                    
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # Remove 'data: ' prefix
                            if data_str == '[DONE]':
                                print("🏁 Stream completed")
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                print(f"📦 Chunk: {json.dumps(chunk_data, indent=2)}")
                            except json.JSONDecodeError:
                                print(f"📦 Raw chunk: {data_str}")
                    
                    return True
                else:
                    error_text = await response.text()
                    print(f"✗ Error {response.status}: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting chat completions tools tests...")
    
    # Test non-streaming
    success1 = await test_chat_tools()
    
    # Test streaming
    success2 = await test_chat_tools_streaming()
    
    if success1 and success2:
        print("\n🎉 All tools tests passed!")
    else:
        print("\n❌ Some tools tests failed")
        print("Make sure the proxy server is running: python -m asksage_proxy.app")


if __name__ == "__main__":
    asyncio.run(main())