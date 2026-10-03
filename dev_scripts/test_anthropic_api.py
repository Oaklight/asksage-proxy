#!/usr/bin/env python3
"""Test script for Anthropic-compatible endpoints in asksage-proxy."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import aiohttp
from asksage_proxy.app import init_app
from asksage_proxy.config import load_config


async def run_tests():
    config = load_config()
    # Force test port or run in-memory aiohttp test server
    from aiohttp.test_utils import TestServer

    app = await init_app(config)
    server = TestServer(app)
    await server.start_server()

    base_url = str(server.make_url("/")).rstrip("/") + "/"
    print(f"Test server running at {base_url}")

    async with aiohttp.ClientSession() as session:
        # Test 1: Count Tokens
        print("\n--- Test 1: Count Tokens (/v1/messages/count_tokens) ---")
        count_payload = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello, how many tokens is this?"}],
        }
        async with session.post(
            f"{base_url}v1/messages/count_tokens",
            json=count_payload,
            headers={"x-api-key": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Result: {data}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "input_tokens" in data, "Expected input_tokens in response"
            print("✓ Test 1 passed!")

        # Test 2: Non-streaming Messages (Claude model)
        print("\n--- Test 2: Non-streaming Message (Claude model) ---")
        msg_payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 30,
            "messages": [{"role": "user", "content": "Respond with the single word 'PONG'."}],
        }
        async with session.post(
            f"{base_url}v1/messages",
            json=msg_payload,
            headers={"x-api-key": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Result: {data}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert data.get("type") == "message", "Expected type == 'message'"
            assert "content" in data, "Expected content in message"
            print("✓ Test 2 passed!")

        # Test 3: Streaming Messages (Claude model)
        print("\n--- Test 3: Streaming Message (Claude model) ---")
        stream_payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 30,
            "stream": True,
            "messages": [{"role": "user", "content": "Count from 1 to 3."}],
        }
        async with session.post(
            f"{base_url}v1/messages",
            json=stream_payload,
            headers={"x-api-key": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}, Content-Type: {resp.headers.get('Content-Type')}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            event_count = 0
            async for line in resp.content:
                l = line.decode("utf-8").strip()
                if l.startswith("event:"):
                    event_count += 1
                    print(f"  Stream event: {l}")
                elif l.startswith("data:"):
                    print(f"  Stream data: {l[:70]}")
            assert event_count > 0, "Expected at least one SSE event"
            print("✓ Test 3 passed!")

        # Test 4: Non-streaming Messages with non-Claude model (Rosetta fallback test)
        print("\n--- Test 4: Non-Claude model (gpt-4o) with Rosetta fallback ---")
        gpt_payload = {
            "model": "gpt-4o",
            "max_tokens": 20,
            "messages": [{"role": "user", "content": "Say hello in one word."}],
        }
        async with session.post(
            f"{base_url}v1/messages",
            json=gpt_payload,
            headers={"x-api-key": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Result: {data}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert data.get("type") == "message", f"Expected type == 'message', got {data.get('type')}"
        # Test 5: Streaming with non-Claude model (gpt-4o) with Rosetta SSE conversion
        print("\n--- Test 5: Non-Claude model (gpt-4o) Streaming with Rosetta fallback ---")
        gpt_stream_payload = {
            "model": "gpt-4o",
            "max_tokens": 20,
            "stream": True,
            "messages": [{"role": "user", "content": "Count from 1 to 2."}],
        }
        async with session.post(
            f"{base_url}v1/messages",
            json=gpt_stream_payload,
            headers={"x-api-key": "dummy"},
        ) as resp:
            print(f"Status: {resp.status}, Content-Type: {resp.headers.get('Content-Type')}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            event_count = 0
            async for line in resp.content:
                l = line.decode("utf-8").strip()
                if l.startswith("event:"):
                    event_count += 1
                    print(f"  Stream event: {l}")
                elif l.startswith("data:"):
                    print(f"  Stream data: {l[:70]}")
            assert event_count > 0, "Expected at least one SSE event in stream"
            print("✓ Test 5 passed!")

        # Test 6: Official Anthropic SDK client test
        print("\n--- Test 6: Official Anthropic SDK client test ---")
        try:
            import anthropic
            async with anthropic.AsyncAnthropic(base_url=base_url, api_key="dummy") as sdk_client:
                resp = await sdk_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=20,
                    messages=[{"role": "user", "content": "Respond with 'SDK_OK'."}],
                )
                print(f"SDK Response: {resp.content[0].text}")
                assert len(resp.content[0].text) > 0
                print("✓ Test 6 (Official Anthropic SDK) passed!")
        except Exception as e:
            print(f"SDK test error: {e}")
            raise

    await server.close()
    print("\n🎉 ALL ANTHROPIC TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
