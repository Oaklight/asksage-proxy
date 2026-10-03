#!/usr/bin/env python3
"""Test script for Gemini-compatible endpoints in asksage-proxy."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import aiohttp
from aiohttp.test_utils import TestServer
from asksage_proxy.app import init_app
from asksage_proxy.config import load_config


async def run_tests():
    config = load_config()

    app = await init_app(config)
    server = TestServer(app)
    await server.start_server()

    base_url = str(server.make_url("/")).rstrip("/") + "/"
    print(f"Test server running at {base_url}")

    async with aiohttp.ClientSession() as session:
        # Test 1: Non-streaming generateContent
        print("\n--- Test 1: Non-streaming generateContent ---")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Respond with the word 'PONG'."}],
                }
            ]
        }
        url = f"{base_url}v1beta/models/google-gemini-2.5-pro:generateContent"
        async with session.post(
            url,
            json=payload,
            headers={"x-access-tokens": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Result: {data}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "candidates" in data, "Expected 'candidates' in response"
            assert len(data["candidates"]) > 0, "Expected non-empty candidates"
            print("✓ Test 1 passed!")

        # Test 2: Streaming streamGenerateContent
        print("\n--- Test 2: Streaming streamGenerateContent ---")
        stream_url = f"{base_url}v1beta/models/google-gemini-2.5-pro:streamGenerateContent"
        stream_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Count from 1 to 3."}],
                }
            ]
        }
        async with session.post(
            stream_url,
            json=stream_payload,
            headers={"x-access-tokens": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}, Content-Type: {resp.headers.get('Content-Type')}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            chunk_count = 0
            async for chunk in resp.content.iter_any():
                chunk_count += 1
                print(f"  Chunk {chunk_count}: {chunk[:70]}")
                if chunk_count >= 3:
                    break
            assert chunk_count > 0, "Expected stream chunks"
            print("✓ Test 2 passed!")

        # Test 3: Model path normalization with prefix
        print("\n--- Test 3: Model path normalization (publishers/google/models/) ---")
        prefix_url = f"{base_url}v1beta/models/publishers/google/models/google-gemini-2.5-pro:generateContent"
        async with session.post(
            prefix_url,
            json=payload,
            headers={"x-access-tokens": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "candidates" in data
            print("✓ Test 3 passed!")

        # Test 4: Non-Gemini model (gpt-4o) with Rosetta fallback
        print("\n--- Test 4: Non-Gemini model (gpt-4o) with Rosetta fallback ---")
        gpt_url = f"{base_url}v1beta/models/gpt-4o:generateContent"
        async with session.post(
            gpt_url,
            json=payload,
            headers={"x-access-tokens": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Result: {data}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "candidates" in data, "Expected candidates in Rosetta converted response"
            print("✓ Test 4 passed!")

    await server.close()
    print("\n🎉 ALL GEMINI TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
