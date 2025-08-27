#!/usr/bin/env python3
"""Test script using the ANL provided client to verify it gets real content."""

import os
import sys
from pathlib import Path

# Add anl_provided to path
sys.path.insert(0, str(Path(__file__).parent.parent / "anl_provided"))

from loguru import logger

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not available, try to load manually
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

from anl_asksage_client import ANLAskSageClient


def test_anl_client():
    """Test the ANL provided client to see if it gets real content."""
    
    # Get API key and email from environment
    api_key = os.getenv("ASKSAGE_API_KEY")
    email = os.getenv("ASKSAGE_EMAIL", "test@example.com")
    
    if not api_key:
        logger.error("ASKSAGE_API_KEY environment variable not set")
        return
    
    logger.info(f"Using email: {email}")
    
    try:
        # Get certificate path
        cert_path = str(Path(__file__).parent.parent / "anl_provided" / "asksage_anl_gov.pem")
        
        # Create ANL client with certificate
        with ANLAskSageClient(
            email=email,
            api_key=api_key,
            # Use default URLs
            user_base_url="https://api.asksage.anl.gov/user",
            server_base_url="https://api.asksage.anl.gov/server",
            path_to_CA_Bundle=cert_path,
        ) as client:
            
            logger.info("ANL Client initialized successfully")
            
            # Test 1: Simple query with authorized model
            logger.info("Testing simple query with claude-4-sonnet...")
            response1 = client.query(
                message="What is 2+2?",
                model="claude-4-sonnet",
                temperature=0.7
            )
            logger.info(f"Simple query response: {response1}")
            
            # Test 2: Query with system prompt
            logger.info("Testing query with system prompt...")
            response2 = client.query(
                message="Tell me a short joke",
                system_prompt="You are a helpful and funny assistant.",
                model="claude-4-sonnet",
                temperature=0.8
            )
            logger.info(f"System prompt query response: {response2}")
            
            # Test 3: Query with different parameters
            logger.info("Testing query with different parameters...")
            response3 = client.query(
                message="What is the capital of France?",
                model="gpt-4o",
                temperature=0.1,
                limit_references=3,
                dataset="all"
            )
            logger.info(f"Detailed query response: {response3}")
            
            # Test 4: Get models to verify API connectivity
            logger.info("Testing get_models...")
            models = client.get_models()
            logger.info(f"Available models: {models}")
            
    except Exception as e:
        logger.error(f"ANL Client test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    logger.info("Testing ANL provided client...")
    test_anl_client()
    logger.info("ANL client test completed")