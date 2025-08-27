#!/usr/bin/env python3
"""Test script to verify direct API key authentication works."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from asksage_proxy.client import AskSageClient
from asksage_proxy.config import AskSageConfig


async def test_simple_auth():
    """Test direct API key authentication."""
    
    # Create a simple config using the same env var as ANL client
    config = AskSageConfig(
        api_key=os.getenv("ASK_SAGE_API", "dummy-key"),
        asksage_server_base_url="https://api.asksage.anl.gov/server",
        asksage_user_base_url="https://api.asksage.anl.gov/user",
        timeout_seconds=30,
    )
    
    print(f"Testing with API key: {config.api_key[:10]}...")
    
    try:
        async with AskSageClient(config) as client:
            print("✓ Client initialized successfully")
            
            # Test get models
            print("Testing get_models...")
            models = await client.get_models()
            print(f"✓ Got models: {list(models.keys()) if isinstance(models, dict) else models}")
            
            # Test simple query
            print("Testing query...")
            payload = {
                "message": "What is the capital of France?",
                "model": "gpt-4o",
                "temperature": 0.0,
                "persona": "default",
                "dataset": "all",
                "live": 0,
            }
            
            response = await client.query(payload)
            print(f"✓ Query response: {response}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_simple_auth())
    if success:
        print("\n🎉 Simple authentication works!")
    else:
        print("\n❌ Simple authentication failed")