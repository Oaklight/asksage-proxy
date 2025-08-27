#!/usr/bin/env python3
"""Test script for chat completions endpoint."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from asksage_proxy.endpoints.chat import transform_openai_to_asksage, transform_asksage_to_openai


async def test_transformation_functions():
    """Test the transformation functions directly."""
    
    logger.info("Testing transformation functions...")
    
    # Test OpenAI to AskSage transformation
    openai_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    asksage_payload = await transform_openai_to_asksage(openai_request)
    logger.info(f"OpenAI request transformed to AskSage:")
    logger.info(f"{json.dumps(asksage_payload, indent=2)}")
    
    # Test AskSage to OpenAI transformation - format 1 (direct response)
    asksage_response_1 = {
        "response": "The capital of France is Paris.",
        "status": 200
    }
    
    openai_response_1 = await transform_asksage_to_openai(
        asksage_response_1,
        model_name="gpt-4",
        create_timestamp=1234567890,
        prompt_tokens=20,
        is_streaming=False
    )
    logger.info(f"AskSage response (format 1) transformed to OpenAI:")
    logger.info(f"{json.dumps(openai_response_1, indent=2)}")
    
    # Test AskSage to OpenAI transformation - format 2 (nested response)
    asksage_response_2 = {
        "response": {
            "response": "The capital of France is Paris.",
            "message": "Generated response message.",
            "embedding_down": False,
            "vectors_down": False,
            "uuid": "12345-67890",
            "references": "Some references",
            "teach": False,
            "status": 200
        },
        "status": 200
    }
    
    openai_response_2 = await transform_asksage_to_openai(
        asksage_response_2,
        model_name="gpt-4",
        create_timestamp=1234567890,
        prompt_tokens=20,
        is_streaming=False
    )
    logger.info(f"AskSage response (format 2) transformed to OpenAI:")
    logger.info(f"{json.dumps(openai_response_2, indent=2)}")
    
    # Test streaming response
    streaming_response = await transform_asksage_to_openai(
        asksage_response_1,
        model_name="gpt-4",
        create_timestamp=1234567890,
        prompt_tokens=20,
        is_streaming=True
    )
    logger.info(f"Streaming response:")
    logger.info(f"{json.dumps(streaming_response, indent=2)}")


async def test_conversation_format():
    """Test conversation format transformation."""
    
    logger.info("Testing conversation format...")
    
    # Test multi-turn conversation
    conversation_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you! How can I help you today?"},
            {"role": "user", "content": "Can you tell me about Python?"}
        ],
        "temperature": 0.5
    }
    
    asksage_payload = await transform_openai_to_asksage(conversation_request)
    logger.info(f"Conversation transformed to AskSage:")
    logger.info(f"{json.dumps(asksage_payload, indent=2)}")


async def test_tools_format():
    """Test tools/function calling format."""
    
    logger.info("Testing tools format...")
    
    # Test with tools
    tools_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "What's the weather like in Paris?"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ],
        "tool_choice": "auto"
    }
    
    asksage_payload = await transform_openai_to_asksage(tools_request)
    logger.info(f"Tools request transformed to AskSage:")
    logger.info(f"{json.dumps(asksage_payload, indent=2)}")


async def main():
    """Main test function."""
    logger.info("Starting chat endpoint transformation tests...")
    
    try:
        await test_transformation_functions()
        await test_conversation_format()
        await test_tools_format()
        
        logger.info("All transformation tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())